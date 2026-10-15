import logging
import mimetypes
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.core.filesystem import identity, stored_identity, protection, volume_key, IMAGE_EXTENSIONS
from app.database.models import ScanJob, ScanRoot, Volume, File, MediaMetadata, FileHash, now
from app.hashing.sha256 import hash_file, ScanStopped
from app.metadata.extract import extract
from app.scanner.discovery import discover
from app.grouping.exact import build_groups

log = logging.getLogger("media_cleaner.scan")


class JobManager:
    def __init__(self, sessions):
        self.sessions = sessions
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")
        self.shutdown_event = threading.Event()
        self.lock = threading.RLock()
        self.active = None
        with sessions.begin() as session:
            for job in session.scalars(select(ScanJob).where(ScanJob.status.in_(["running", "queued"]))):
                job.status = "interrupted"
                job.stage = "Restart interrupted this scan; resume explicitly"

    def start(self, scan_id: str):
        with self.lock:
            if self.active and not self.active.done():
                raise ValueError("Another scan is active; pause or cancel it first")
            self.active = self.executor.submit(self.run, scan_id)

    def checkpoint(self, scan_id: str):
        if self.shutdown_event.is_set():
            raise ScanStopped()
        with self.sessions() as session:
            job = session.get(ScanJob, scan_id)
            if job.status not in {"queued", "running"}:
                raise ScanStopped()

    def run(self, scan_id: str):
        log.info("scan_started", extra={"scan_id": scan_id})
        try:
            with self.sessions.begin() as session:
                job = session.get(ScanJob, scan_id)
                job.status, job.stage = "running", "discovery"
                options = job.options

            def checkpoint():
                self.checkpoint(scan_id)

            def record_error(message):
                with self.sessions.begin() as session:
                    job = session.get(ScanJob, scan_id)
                    job.errors += 1
                    job.error = message

            for root_text in options["roots"]:
                checkpoint()
                root = Path(root_text)
                try:
                    key, mount = volume_key(root)
                    with self.sessions.begin() as session:
                        root_record = session.scalar(
                            select(ScanRoot).where(ScanRoot.scan_id == scan_id, ScanRoot.path == root_text)
                        )
                        if root_record and root_record.volume_id != key:
                            raise ValueError("Volume identity changed; start a new scan")
                        if not session.get(Volume, key):
                            session.add(Volume(id=key, device=str(root.stat().st_dev), mount_path=mount))
                            session.flush()
                        if not root_record:
                            session.add(ScanRoot(scan_id=scan_id, path=root_text, volume_id=key))
                    for path in discover(root, options, checkpoint, record_error):
                        try:
                            expected = identity(path)
                            with self.sessions.begin() as session:
                                file = session.scalar(
                                    select(File).where(File.scan_id == scan_id, File.path == str(path))
                                )
                                if file:
                                    # Restart enumerates; hashes are revalidated below rather than trusting old snapshots.
                                    continue
                                session.add(
                                    File(
                                        scan_id=scan_id,
                                        volume_id=key,
                                        path=str(path),
                                        relative_path=str(path.relative_to(root)),
                                        name=path.name,
                                        extension=path.suffix.lower(),
                                        media_type="image"
                                        if path.suffix.lower() in IMAGE_EXTENSIONS
                                        else "video",
                                        mime_type=mimetypes.guess_type(path.name)[0]
                                        or "application/octet-stream",
                                        size=expected.size,
                                        device=expected.device,
                                        inode=expected.inode,
                                        mtime_ns=expected.mtime_ns,
                                        ctime_ns=expected.ctime_ns,
                                        birthtime=getattr(path.stat(), "st_birthtime", None),
                                        protected_reason=protection(path, options["protected_directories"]),
                                    )
                                )
                                session.get(ScanJob, scan_id).discovered += 1
                        except IntegrityError:
                            # A second path to the same inode (hard link or overlapping root).
                            pass
                        except (OSError, ValueError) as exc:
                            record_error(type(exc).__name__)
                except (OSError, ValueError) as exc:
                    record_error(str(exc))
                    with self.sessions.begin() as session:
                        record = session.scalar(
                            select(ScanRoot).where(ScanRoot.scan_id == scan_id, ScanRoot.path == root_text)
                        )
                        if record:
                            record.available = False
                    raise ValueError("A scan root is unavailable or changed; history was retained") from exc
            with self.sessions.begin() as session:
                session.get(ScanJob, scan_id).stage = "metadata_and_hashing"
            # Process every file's metadata, hash only size candidates. The queue is bounded.
            with ThreadPoolExecutor(max_workers=options["concurrency"], thread_name_prefix="media") as pool:
                pending = set()
                last_id = ""
                while True:
                    checkpoint()
                    with self.sessions() as session:
                        page = session.scalars(
                            select(File)
                            .where(File.scan_id == scan_id, File.id > last_id)
                            .order_by(File.id)
                            .limit(128)
                        ).all()
                    if not page:
                        break
                    for file in page:
                        checkpoint()
                        last_id = file.id
                        pending.add(pool.submit(self.process_file, scan_id, file.id, checkpoint))
                        if len(pending) >= options["concurrency"] * 2:
                            done, pending = wait(pending, return_when=FIRST_COMPLETED)
                            for future in done:
                                future.result()
                    del page
                for future in pending:
                    future.result()
            checkpoint()
            for root_text in options["roots"]:
                try:
                    current_key, _ = volume_key(Path(root_text))
                    if not Path(root_text).is_dir():
                        raise ValueError("Root disconnected")
                    with self.sessions() as session:
                        saved_root = session.scalar(
                            select(ScanRoot).where(ScanRoot.scan_id == scan_id, ScanRoot.path == root_text)
                        )
                        if saved_root.volume_id != current_key:
                            raise ValueError("Root volume changed")
                except (OSError, ValueError):
                    with self.sessions.begin() as session:
                        saved_root = session.scalar(
                            select(ScanRoot).where(ScanRoot.scan_id == scan_id, ScanRoot.path == root_text)
                        )
                        saved_root.available = False
                    raise ValueError("Root disconnected or changed; history retained")
            with self.sessions() as session:
                job = session.get(ScanJob, scan_id)
                job.stage = "grouping"
                session.commit()
                build_groups(session, scan_id, checkpoint)
                checkpoint()
                session.refresh(job)
                job.status, job.stage, job.updated_at = "completed", "complete", now()
                session.commit()
            log.info("scan_completed", extra={"scan_id": scan_id})
        except ScanStopped:
            with self.sessions.begin() as session:
                job = session.get(ScanJob, scan_id)
                if job.status in {"running", "queued"}:
                    job.status = "interrupted"
                job.updated_at = now()
        except Exception as exc:
            log.exception("scan_failed", extra={"scan_id": scan_id})
            with self.sessions.begin() as session:
                job = session.get(ScanJob, scan_id)
                job.status, job.error, job.updated_at = "failed", str(exc), now()

    def process_file(self, scan_id, file_id, checkpoint):
        checkpoint()
        with self.sessions() as session:
            file = session.get(File, file_id)
            path, expected = Path(file.path), stored_identity(file)
            candidate = (
                session.scalar(
                    select(func.count())
                    .select_from(File)
                    .where(File.scan_id == scan_id, File.size == file.size)
                )
                > 1
            )
            key = expected.key(file.path)
            cached = session.get(FileHash, key)
            media_type = file.media_type
        try:
            if identity(path) != expected:
                raise ValueError("File changed since discovery; start a new scan")
            digest = None
            if cached:
                fields, warnings = cached.metadata_fields, cached.metadata_warnings
                if candidate:
                    digest = cached.digest or hash_file(path, expected, checkpoint)
            else:
                fields, warnings = extract(path, media_type)
                if candidate:
                    digest = hash_file(path, expected, checkpoint)
            if identity(path) != expected:
                raise ValueError("File changed while processing")
            with self.sessions.begin() as session:
                file = session.get(File, file_id)
                file.sha256, file.status, file.error = digest, "ready", None
                old = session.get(MediaMetadata, file_id)
                if old:
                    old.fields, old.warnings = fields, warnings
                else:
                    session.add(MediaMetadata(file_id=file_id, fields=fields, warnings=warnings))
                cache_entry = session.get(FileHash, key)
                if cache_entry:
                    if digest:
                        cache_entry.digest = digest
                else:
                    session.add(
                        FileHash(
                            cache_key=key, digest=digest, metadata_fields=fields, metadata_warnings=warnings
                        )
                    )
                job = session.get(ScanJob, scan_id)
                job.processed += 1
                job.bytes_processed += expected.size
                job.cache_hits += int(cached is not None)
                job.updated_at = now()
        except ScanStopped:
            raise
        except Exception as exc:
            with self.sessions.begin() as session:
                file = session.get(File, file_id)
                file.status, file.error, file.sha256 = "error", str(exc), None
                job = session.get(ScanJob, scan_id)
                job.errors += 1
                job.processed += 1

    def close(self):
        self.shutdown_event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
