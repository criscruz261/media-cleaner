import logging
import mimetypes
import threading
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.core.filesystem import identity, stored_identity, protection, volume_key, IMAGE_EXTENSIONS
from app.database.models import (
    ScanJob,
    ScanRoot,
    Volume,
    File,
    MediaMetadata,
    FileHash,
    Fingerprint,
    FileReviewChoice,
    now,
)
from app.hashing.sha256 import hash_file, ScanStopped
from app.metadata.extract import extract
from app.core.media_tools import executable
from app.scanner.discovery import discover
from app.scanner import folder_cache
from app.grouping.live import LiveMatcher
from app.similarity.images import fingerprint_image, ALGORITHM, VERSION
from app.similarity import temporal

log = logging.getLogger("media_cleaner.scan")


class JobManager:
    def __init__(self, sessions):
        self.sessions = sessions
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")
        self.shutdown_event = threading.Event()
        self.lock = threading.RLock()
        self.active = None
        self.active_id = None
        self.stopping = False
        self.checkpointing = set()
        self.activity_lock = threading.Lock()
        self.activities = {}
        self.matcher_dirty = False
        with sessions.begin() as session:
            for job in session.scalars(select(ScanJob).where(ScanJob.status.in_(["running", "queued"]))):
                job.status = "interrupted"
                job.stage = "Restart interrupted this scan; resume explicitly"

    def activity(self, scan_id):
        with self.activity_lock:
            return [dict(value) for (job_id, _), value in self.activities.items() if job_id == scan_id]

    def update_activity(self, scan_id, file_id, **values):
        with self.activity_lock:
            self.activities.setdefault((scan_id, file_id), {"file_id": file_id}).update(values)

    def clear_activity(self, scan_id, file_id):
        with self.activity_lock:
            self.activities.pop((scan_id, file_id), None)

    def start(self, scan_id: str):
        with self.lock:
            if self.stopping:
                raise ValueError("App shutdown is in progress")
            if scan_id in self.checkpointing:
                raise ValueError("Checkpoint is still being saved")
            if self.active and not self.active.done():
                raise ValueError("Another scan is active; pause or cancel it first")
            self.active_id = scan_id
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
        matcher = None
        try:
            with self.lock, self.sessions.begin() as session:
                job = session.get(ScanJob, scan_id)
                if self.stopping or job.status not in {"queued", "running"}:
                    raise ScanStopped()
                job.status, job.stage = "running", "discovery"
                options = job.options
                job.processed = session.scalar(
                    select(func.count())
                    .select_from(File)
                    .where(
                        File.scan_id == scan_id,
                        File.status.in_(["ready", "error", "trashed", "quarantined", "restored"]),
                    )
                )
                job.bytes_processed = session.scalar(
                    select(func.coalesce(func.sum(File.size), 0)).where(
                        File.scan_id == scan_id,
                        File.status.in_(["ready", "trashed", "quarantined", "restored"]),
                    )
                )

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
                                job = session.get(ScanJob, scan_id)
                                job.discovered += 1
                                job.total_bytes += expected.size
                                job.updated_at = now()
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
            with self.lock:
                matcher = LiveMatcher(self.sessions, scan_id, options, checkpoint)
                self.matcher_dirty = False

            def publish(file_id=None):
                nonlocal matcher
                with self.lock:
                    if self.matcher_dirty:
                        matcher.close()
                        matcher = LiveMatcher(self.sessions, scan_id, options, checkpoint)
                        last_ready = ""
                        while True:
                            with self.sessions() as session:
                                ready_ids = session.scalars(
                                    select(File.id)
                                    .where(
                                        File.scan_id == scan_id, File.status == "ready", File.id > last_ready
                                    )
                                    .order_by(File.id)
                                    .limit(128)
                                ).all()
                            if not ready_ids:
                                break
                            for ready_id in ready_ids:
                                matcher.add(ready_id)
                            last_ready = ready_ids[-1]
                        self.matcher_dirty = False
                    if file_id is not None:
                        matcher.add(file_id)

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
                                publish(future.result())
                    del page
                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        publish(future.result())
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
            with self.lock, self.sessions() as session:
                publish()
                job = session.get(ScanJob, scan_id)
                job.stage = "grouping"
                session.commit()
                matcher.finish()
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
        finally:
            if matcher is not None:
                matcher.close()

    def process_file(self, scan_id, file_id, checkpoint):
        checkpoint()
        with self.sessions() as session:
            file = session.get(File, file_id)
            if file.status not in {"discovered", "ready", "error"}:
                return file_id
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
            was_ready = file.status == "ready"
            was_processed = file.status in {"ready", "error"}
            media_type = file.media_type
            options = session.get(ScanJob, scan_id).options
            similar = options["mode"] == "similar"
            candidate = candidate or similar
            sequence = similar and temporal.temporal_kind(path, media_type)
            algorithm, version = (temporal.ALGORITHM, temporal.VERSION) if sequence else (ALGORITHM, VERSION)
            descriptor = None
            previous = (
                session.scalar(
                    select(Fingerprint)
                    .where(
                        Fingerprint.cache_key == key,
                        Fingerprint.algorithm == algorithm,
                        Fingerprint.version == version,
                        (
                            func.coalesce(Fingerprint.value["sample_count"].as_integer(), 9)
                            == options.get("video_samples", 9)
                        )
                        if sequence
                        else True,
                    )
                    .limit(1)
                )
                if similar
                else None
            )
            # Resume may reuse this job's completed checkpoints, while new files
            # in a from-scratch scan must bypass both database and folder caches.
            recompute = options.get("force_rescan", False) and not was_ready
            if recompute:
                cached = previous = None
        portable = None if recompute else folder_cache.read(path, options["roots"], key)
        if portable:
            if not cached:
                cached = SimpleNamespace(
                    digest=portable["digest"],
                    metadata_fields=portable["fields"],
                    metadata_warnings=portable["warnings"],
                )
            if similar and previous is None:
                entry = next(
                    (
                        item
                        for item in portable["fingerprints"]
                        if item["algorithm"] == algorithm
                        and item["version"] == version
                        and (
                            not sequence
                            or item["value"].get("sample_count", 9) == options.get("video_samples", 9)
                        )
                    ),
                    None,
                )
                if entry:
                    previous = SimpleNamespace(value=entry["value"])
        if (
            sequence
            and previous is not None
            and previous.value.get("sample_count", 9) != options.get("video_samples", 9)
        ):
            previous = None
        try:
            if identity(path) != expected:
                raise ValueError("File changed since discovery; start a new scan")
            if was_ready and (not candidate or file.sha256) and (not similar or previous is not None):
                with self.sessions.begin() as session:
                    session.get(ScanJob, scan_id).updated_at = now()
                self.save_folder_cache(scan_id, file_id)
                return file_id
            self.update_activity(
                scan_id,
                file_id,
                path=str(path),
                phase="metadata",
                bytes_done=0,
                size=expected.size,
                frames_done=0,
                frames_total=0,
            )

            def hash_progress(value):
                self.update_activity(scan_id, file_id, phase="hashing", bytes_done=value)

            def frame_progress(value, total):
                self.update_activity(
                    scan_id, file_id, phase="comparing frames", frames_done=value, frames_total=total
                )

            digest = None
            if cached:
                fields, warnings = cached.metadata_fields, list(cached.metadata_warnings)
                warnings = [
                    warning
                    for warning in warnings
                    if not warning.startswith(
                        (
                            "Visual comparison unavailable:",
                            "Animated images require",
                            "Too little visual detail",
                            "Not enough informative",
                        )
                    )
                ]
                if media_type == "video" and executable("ffprobe") and not fields.get("duration"):
                    fields, warnings = extract(path, media_type)
                if candidate:
                    digest = cached.digest or hash_file(path, expected, checkpoint, hash_progress)
            else:
                fields, warnings = extract(path, media_type)
                if candidate:
                    digest = hash_file(path, expected, checkpoint, hash_progress)
            metadata_warnings = list(warnings)
            if similar:
                try:
                    if previous:
                        descriptor = previous.value
                    elif sequence:
                        descriptor = (
                            temporal.fingerprint_video(
                                path, checkpoint, frame_progress, options.get("video_samples", 9)
                            )
                            if media_type == "video"
                            else temporal.fingerprint_animation(
                                path, checkpoint, frame_progress, options.get("video_samples", 9)
                            )
                        )
                    else:
                        self.update_activity(scan_id, file_id, phase="comparing image")
                        descriptor = fingerprint_image(path)
                    if sequence:
                        descriptor = {**descriptor, "sample_count": options.get("video_samples", 9)}
                    if "skipped" in descriptor and descriptor["skipped"] not in warnings:
                        warnings = list(warnings) + [descriptor["skipped"]]
                except ScanStopped:
                    raise
                except Exception as exc:
                    warning = f"Visual comparison unavailable: {str(exc) if isinstance(exc, ValueError) else type(exc).__name__}"
                    if warning not in warnings:
                        warnings = list(warnings) + [warning]
            if identity(path) != expected:
                raise ValueError("File changed while processing")
            with self.lock, self.sessions.begin() as session:
                file = session.get(File, file_id)
                if file.status not in {"discovered", "ready", "error"}:
                    return file_id
                file.sha256, file.status, file.error = digest, "ready", None
                if descriptor is not None:
                    saved = session.scalar(
                        select(Fingerprint).where(
                            Fingerprint.file_id == file_id,
                            Fingerprint.algorithm == algorithm,
                            Fingerprint.version == version,
                        )
                    )
                    if saved:
                        saved.value = descriptor
                    else:
                        session.add(
                            Fingerprint(
                                file_id=file_id,
                                algorithm=algorithm,
                                version=version,
                                cache_key=key,
                                value=descriptor,
                            )
                        )
                if portable:
                    for classification, keep in portable["choices"].items():
                        if not session.get(FileReviewChoice, (file_id, classification)):
                            session.add(
                                FileReviewChoice(
                                    file_id=file_id,
                                    classification=classification,
                                    keep=keep or bool(file.protected_reason),
                                )
                            )
                old = session.get(MediaMetadata, file_id)
                if old:
                    old.fields, old.warnings = fields, warnings
                else:
                    session.add(MediaMetadata(file_id=file_id, fields=fields, warnings=warnings))
                cache_entry = session.get(FileHash, key)
                if cache_entry:
                    if digest:
                        cache_entry.digest = digest
                    cache_entry.metadata_fields, cache_entry.metadata_warnings = fields, metadata_warnings
                else:
                    session.add(
                        FileHash(
                            cache_key=key,
                            digest=digest,
                            metadata_fields=fields,
                            metadata_warnings=metadata_warnings,
                        )
                    )
                job = session.get(ScanJob, scan_id)
                job.processed += int(not was_processed)
                job.bytes_processed += 0 if was_ready else expected.size
                job.cache_hits += int(cached is not None and not was_processed)
                job.updated_at = now()
        except ScanStopped:
            raise
        except Exception as exc:
            with self.lock, self.sessions.begin() as session:
                file = session.get(File, file_id)
                if file.status not in {"discovered", "ready", "error"}:
                    return file_id
                file.status, file.error, file.sha256 = "error", str(exc), None
                job = session.get(ScanJob, scan_id)
                job.errors += 1
                job.processed += int(not was_processed)
                if was_ready:
                    job.bytes_processed = max(0, job.bytes_processed - expected.size)
                job.updated_at = now()
        finally:
            self.clear_activity(scan_id, file_id)
        self.save_folder_cache(scan_id, file_id)
        return file_id

    def save_folder_cache(self, scan_id, file_id):
        with self.lock, self.sessions() as session:
            file = session.get(File, file_id)
            if not file or file.status != "ready":
                return
            metadata = session.get(MediaMetadata, file_id)
            job = session.get(ScanJob, scan_id)
            try:
                folder_cache.write(
                    Path(file.path),
                    job.options["roots"],
                    stored_identity(file).key(file.path),
                    {
                        "digest": file.sha256,
                        "fields": metadata.fields if metadata else {},
                        "warnings": metadata.warnings if metadata else [],
                        "fingerprints": [
                            {"algorithm": item.algorithm, "version": item.version, "value": item.value}
                            for item in session.scalars(
                                select(Fingerprint).where(Fingerprint.file_id == file_id)
                            )
                        ],
                        "choices": {
                            item.classification: item.keep
                            for item in session.scalars(
                                select(FileReviewChoice).where(FileReviewChoice.file_id == file_id)
                            )
                        },
                    },
                )
            except (OSError, ValueError) as exc:
                log.warning("folder_cache_unavailable: %s", type(exc).__name__)
                if metadata:
                    warning = "Folder cache unavailable; checkpoints are still saved in the app database."
                    if warning not in metadata.warnings:
                        metadata.warnings = list(metadata.warnings) + [warning]
                        session.commit()

    def pause_at_checkpoint(self, scan_id, stop=False):
        with self.lock, self.sessions.begin() as session:
            job = session.get(ScanJob, scan_id)
            if not job or job.status not in {"queued", "running", "paused", "interrupted"}:
                raise ValueError("This scan cannot be paused at a checkpoint")
            self.checkpointing.add(scan_id)
            job.status, job.stage, job.updated_at = (
                "paused",
                "Stopping scan; saving checkpoint" if stop else "Saving checkpoint",
                now(),
            )
            active = self.active if self.active_id == scan_id else None
        try:
            # The coordinator may need the lock while its workers unwind.
            if active:
                active.result()
            if stop:
                # Workers may finish a checkpoint before the coordinator publishes
                # its match. Stop has no resume step, so index all saved results now.
                with self.lock:
                    with self.sessions.begin() as session:
                        job = session.get(ScanJob, scan_id)
                        job.stage = "Finalizing completed results before stop"
                        options = job.options
                    matcher = LiveMatcher(self.sessions, scan_id, options, lambda: None)
                    try:
                        last_id = ""
                        while True:
                            with self.sessions() as session:
                                ready_ids = session.scalars(
                                    select(File.id)
                                    .where(
                                        File.scan_id == scan_id,
                                        File.status == "ready",
                                        File.id > last_id,
                                    )
                                    .order_by(File.id)
                                    .limit(128)
                                ).all()
                            if not ready_ids:
                                break
                            for file_id in ready_ids:
                                matcher.add(file_id)
                            last_id = ready_ids[-1]
                        matcher.finish()
                    finally:
                        matcher.close()
            with self.sessions.begin() as session:
                job = session.get(ScanJob, scan_id)
                job.status = "cancelled" if stop else "paused"
                job.stage = (
                    "Scan stopped; completed results and checkpoints saved"
                    if stop
                    else "Checkpoint saved; ready to resume"
                )
                job.updated_at = now()
        finally:
            with self.lock:
                self.checkpointing.discard(scan_id)

    def prepare_shutdown(self):
        with self.lock:
            self.stopping = True
            with self.sessions.begin() as session:
                for job in session.scalars(select(ScanJob).where(ScanJob.status.in_(["running", "queued"]))):
                    job.status, job.stage, job.updated_at = "paused", "Saving checkpoint for shutdown", now()
        self.close()
        with self.sessions.begin() as session:
            for job in session.scalars(select(ScanJob).where(ScanJob.status == "paused")):
                job.stage, job.updated_at = "Checkpoint saved; resume after reopening the app", now()

    def close(self):
        self.shutdown_event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
