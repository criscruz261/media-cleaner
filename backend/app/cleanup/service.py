from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import logging
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from send2trash import send2trash
from app.core.filesystem import identity, stored_identity, protection
from app.database.models import File, DuplicateGroup, GroupMember, CleanupOperation, ScanJob, now
from app.hashing.sha256 import hash_file


log = logging.getLogger("media_cleaner.cleanup")


class CleanupService:
    def __init__(self, sessions, settings):
        self.sessions = sessions
        self.settings = settings

    def validate(self, session, ids: list[str], rehash: bool, group_id: str | None = None) -> list[dict]:
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Choose one or more distinct files")
        active_id = session.scalar(select(ScanJob.id).where(ScanJob.status.in_(["running", "queued"])))
        items = []
        for file_id in ids:
            file = session.get(File, file_id)
            if not file or file.status != "ready" or not file.sha256:
                raise ValueError("File is unavailable or not a verified duplicate")
            if active_id and active_id != file.scan_id:
                raise ValueError("Pause the other active scan before cleanup")
            membership_query = (
                select(GroupMember)
                .join(DuplicateGroup)
                .where(GroupMember.file_id == file_id)
                .order_by(DuplicateGroup.classification)
            )
            if group_id:
                membership_query = membership_query.where(GroupMember.group_id == group_id)
            member = session.scalar(membership_query.limit(1))
            if not member or member.keep:
                raise ValueError("Only files explicitly unchecked during review may be cleaned up")
            group = session.get(DuplicateGroup, member.group_id)
            approximate = group.classification != "EXACT_DUPLICATE"
            if approximate and (not group_id or group.review_status != "reviewed"):
                raise ValueError("Similar photos require manual review and an explicit group cleanup plan")
            path = Path(file.path)
            reason = file.protected_reason or protection(path, self.settings().protected_directories)
            if reason:
                raise ValueError(f"Protected file: {reason}")
            if identity(path) != stored_identity(file):
                raise ValueError("File changed since scanning; scan again")
            keepers = session.scalars(
                select(File)
                .join(GroupMember, GroupMember.file_id == File.id)
                .where(
                    GroupMember.group_id == member.group_id,
                    GroupMember.keep.is_(True),
                    File.status == "ready",
                    File.id.not_in(ids),
                )
            ).all()
            if not keepers:
                raise ValueError("Keep at least one verified file in every group")
            keeper = next(
                (candidate for candidate in keepers if approximate or candidate.sha256 == file.sha256), None
            )
            if not keeper or identity(Path(keeper.path)) != stored_identity(keeper):
                raise ValueError("Retained copy is missing or changed; scan again")
            if rehash:
                if hash_file(path, stored_identity(file)) != file.sha256:
                    raise ValueError("Selected file content changed")
                if hash_file(Path(keeper.path), stored_identity(keeper)) != keeper.sha256:
                    raise ValueError("Retained file content changed")
            items.append(
                {
                    "file_id": file.id,
                    "source": file.path,
                    "size": file.size,
                    "sha256": file.sha256,
                    "keeper_id": keeper.id,
                    "group_id": member.group_id,
                    "classification": group.classification,
                    "keeper": keeper.path,
                    "status": "planned",
                    "quarantine_path": None,
                    "error": None,
                }
            )
        return items

    def plan(self, ids: list[str], destination: str, group_id: str | None = None):
        if destination not in {"trash", "quarantine"}:
            raise ValueError("Choose Trash or same-volume quarantine; permanent deletion is unavailable")
        with self.sessions.begin() as session:
            items = self.validate(session, ids, rehash=False, group_id=group_id)
            operation = CleanupOperation(
                destination=destination,
                token=secrets.token_urlsafe(32),
                items=items,
                total_bytes=sum(item["size"] for item in items),
                expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            )
            session.add(operation)
            session.flush()
            log.info("cleanup_planned")
            return operation

    def execute(self, operation_id: str, token: str, confirmed: bool):
        with self.sessions.begin() as session:
            operation = session.get(CleanupOperation, operation_id)
            if (
                not operation
                or operation.status != "planned"
                or not confirmed
                or not secrets.compare_digest(operation.token, token)
            ):
                raise ValueError("A fresh cleanup plan and explicit confirmation are required")
            if datetime.now(timezone.utc) > datetime.fromisoformat(operation.expires_at):
                raise ValueError("Cleanup plan expired; create a new preview")
            ids = [item["file_id"] for item in operation.items]
            # Whole-plan validation completes before any filesystem mutation.
            group_ids = {item.get("group_id") for item in operation.items}
            group_id = next(iter(group_ids)) if len(group_ids) == 1 else None
            fresh = self.validate(session, ids, rehash=True, group_id=group_id)
            if any(old["keeper_id"] != new["keeper_id"] for old, new in zip(operation.items, fresh)):
                raise ValueError("Keep choices changed after this preview; create a new cleanup plan")
            operation.status = "executing"
            destination = operation.destination
            log.info("cleanup_started")
        for index, file_id in enumerate(ids):
            with self.sessions() as session:
                operation = session.get(CleanupOperation, operation_id)
                items = [dict(item) for item in operation.items]
                item = items[index]
                file = session.get(File, file_id)
                try:
                    # Recheck each item and its keeper immediately before moving.
                    fresh = self.validate(session, [file_id], rehash=True, group_id=item.get("group_id"))
                    if fresh[0]["keeper_id"] != item["keeper_id"]:
                        raise ValueError("Retained copy changed after confirmation")
                    if destination == "quarantine":
                        target = (
                            Path(file.path).parent
                            / ".media-cleaner-quarantine"
                            / operation_id
                            / str(uuid4())
                            / file.name
                        )
                        quarantine_root = Path(file.path).parent / ".media-cleaner-quarantine"
                        if (
                            quarantine_root.is_symlink()
                            or quarantine_root.resolve() != quarantine_root.absolute()
                        ):
                            raise ValueError("Quarantine path contains a symlink")
                        target.parent.mkdir(parents=True, exist_ok=False)
                        if target.parent.stat().st_dev != Path(file.path).stat().st_dev:
                            raise ValueError("Quarantine must be on the same volume")
                        item["quarantine_path"] = str(target)
                    item["status"] = "moving"
                    operation.items = items
                    flag_modified(operation, "items")
                    session.commit()  # Durable intent before touching the filesystem.
                    if destination == "trash":
                        send2trash(file.path)
                    else:
                        Path(file.path).rename(target)
                    item["status"] = "moved"
                    log.info("cleanup_item_moved")
                    file.status = "trashed" if destination == "trash" else "quarantined"
                except Exception as exc:
                    item["status"], item["error"] = "failed", str(exc)
                    log.warning("cleanup_item_failed")
                operation.items = [dict(value) for value in items]
                flag_modified(operation, "items")
                session.commit()
        with self.sessions.begin() as session:
            operation = session.get(CleanupOperation, operation_id)
            operation.status = (
                "completed" if all(item["status"] == "moved" for item in operation.items) else "partial"
            )
            operation.completed_at = now()
            log.info("cleanup_finished")
            affected = {item["file_id"] for item in operation.items if item["status"] == "moved"}
            groups = session.scalars(
                select(DuplicateGroup).join(GroupMember).where(GroupMember.file_id.in_(affected))
            ).all()
            for group in groups:
                live = session.scalars(
                    select(File)
                    .join(GroupMember, GroupMember.file_id == File.id)
                    .where(GroupMember.group_id == group.id, File.status == "ready")
                ).all()
                group.member_count = len(live)
                group.recoverable = sum(file.size for file in live) - max(
                    (file.size for file in live), default=0
                )
                if len(live) < 2:
                    group.review_status = "resolved"
            return operation

    def restore(self, operation_id: str):
        with self.sessions() as session:
            operation = session.get(CleanupOperation, operation_id)
            if (
                not operation
                or operation.destination != "quarantine"
                or operation.status not in {"completed", "partial", "interrupted"}
            ):
                raise ValueError(
                    "Only quarantined operations can be restored here; use the OS for Trash recovery"
                )
            items = [dict(item) for item in operation.items]
            for item in items:
                if item["status"] not in {"moved", "moving"} or not item.get("quarantine_path"):
                    continue
                try:
                    source, target = Path(item["quarantine_path"]), Path(item["source"])
                    if target.exists() or target.is_symlink():
                        raise ValueError("Original path is occupied; restore will never overwrite it")
                    if target.parent.resolve(strict=True) != target.parent:
                        raise ValueError("Original parent changed or is a symlink")
                    if hash_file(source, identity(source)) != item["sha256"]:
                        raise ValueError("Quarantined content changed")
                    # Hard-link + unlink provides no-overwrite semantics on the same volume.
                    target.hardlink_to(source)
                    source.unlink()
                    item["status"], item["error"] = "restored", None
                    log.info("cleanup_item_restored")
                    session.get(File, item["file_id"]).status = "restored"
                except Exception as exc:
                    item["error"] = str(exc)
                operation.items = [dict(value) for value in items]
                flag_modified(operation, "items")
                session.commit()
            operation.status = (
                "restored" if all(item["status"] in {"restored", "failed"} for item in items) else "partial"
            )
            session.commit()
            return operation

    def recover_interrupted(self):
        with self.sessions.begin() as session:
            for operation in session.scalars(
                select(CleanupOperation).where(CleanupOperation.status == "executing")
            ):
                operation.status = "interrupted"
                # Moving records retain source/destination and digest for explicit recovery.
