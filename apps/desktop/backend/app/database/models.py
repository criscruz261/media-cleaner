from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import ForeignKey, Index, UniqueConstraint, JSON, String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Volume(Base):
    __tablename__ = "volumes"
    id: Mapped[str] = mapped_column(primary_key=True)
    device: Mapped[str]
    mount_path: Mapped[str]
    last_seen: Mapped[str] = mapped_column(default=now)


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    status: Mapped[str] = mapped_column(default="queued", index=True)
    options: Mapped[dict] = mapped_column(JSON)
    stage: Mapped[str] = mapped_column(default="queued")
    discovered: Mapped[int] = mapped_column(default=0)
    processed: Mapped[int] = mapped_column(default=0)
    bytes_processed: Mapped[int] = mapped_column(default=0)
    total_bytes: Mapped[int] = mapped_column(default=0)
    cache_hits: Mapped[int] = mapped_column(default=0)
    errors: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


class ScanRoot(Base):
    __tablename__ = "scan_roots"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scan_jobs.id"), index=True)
    path: Mapped[str]
    volume_id: Mapped[str] = mapped_column(ForeignKey("volumes.id"))
    available: Mapped[bool] = mapped_column(default=True)


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("scan_id", "path"),
        UniqueConstraint("scan_id", "device", "inode"),
        Index("ix_files_size_hash", "scan_id", "size", "sha256"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scan_jobs.id"), index=True)
    volume_id: Mapped[str] = mapped_column(ForeignKey("volumes.id"))
    path: Mapped[str]
    relative_path: Mapped[str]
    name: Mapped[str]
    extension: Mapped[str]
    media_type: Mapped[str]
    mime_type: Mapped[str]
    size: Mapped[int]
    device: Mapped[str]
    inode: Mapped[str]
    mtime_ns: Mapped[str]
    ctime_ns: Mapped[str]
    birthtime: Mapped[float | None]
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(default="discovered")
    error: Mapped[str | None]
    protected_reason: Mapped[str | None]
    last_scanned: Mapped[str] = mapped_column(default=now)


class MediaMetadata(Base):
    __tablename__ = "media_metadata"
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), primary_key=True)
    fields: Mapped[dict] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON, default=list)


class FileHash(Base):
    __tablename__ = "file_hashes"
    cache_key: Mapped[str] = mapped_column(primary_key=True)
    algorithm: Mapped[str] = mapped_column(default="sha256-v1")
    digest: Mapped[str | None]
    metadata_fields: Mapped[dict] = mapped_column(JSON)
    metadata_warnings: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)


class DuplicateGroup(Base):
    first_seen_at: Mapped[str | None] = mapped_column(index=True)
    __tablename__ = "duplicate_groups"
    updated_at: Mapped[str] = mapped_column(default=now, index=True)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scan_jobs.id"), index=True)
    classification: Mapped[str] = mapped_column(default="EXACT_DUPLICATE")
    evidence: Mapped[dict] = mapped_column(JSON)
    recommended_id: Mapped[str | None] = mapped_column(ForeignKey("files.id"))
    recommendation: Mapped[str]
    recoverable: Mapped[int]
    member_count: Mapped[int]
    review_status: Mapped[str] = mapped_column(default="unreviewed")


class GroupMember(Base):
    __tablename__ = "group_members"
    group_id: Mapped[str] = mapped_column(ForeignKey("duplicate_groups.id"), primary_key=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), primary_key=True)
    keep: Mapped[bool] = mapped_column(default=True)


class Fingerprint(Base):
    __tablename__ = "fingerprints"
    __table_args__ = (UniqueConstraint("file_id", "algorithm", "version"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"))
    cache_key: Mapped[str | None] = mapped_column(index=True)
    algorithm: Mapped[str]
    version: Mapped[str]
    value: Mapped[dict] = mapped_column(JSON)


class SimilarityMatch(Base):
    __tablename__ = "similarity_matches"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    left_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    right_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    classification: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSON)


class CleanupOperation(Base):
    __tablename__ = "cleanup_operations"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    status: Mapped[str] = mapped_column(default="planned", index=True)
    destination: Mapped[str]
    token: Mapped[str]
    items: Mapped[list] = mapped_column(JSON)
    total_bytes: Mapped[int]
    created_at: Mapped[str] = mapped_column(default=now)
    expires_at: Mapped[str]
    completed_at: Mapped[str | None]


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class FileReviewChoice(Base):
    __tablename__ = "file_review_choices"
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), primary_key=True)
    classification: Mapped[str] = mapped_column(primary_key=True)
    keep: Mapped[bool]


@event.listens_for(DuplicateGroup, "before_insert")
@event.listens_for(DuplicateGroup, "before_update")
def record_first_publication(mapper, connection, group):
    if (
        group.first_seen_at is None
        and group.member_count > 1
        and group.review_status not in {"pending", "resolved"}
    ):
        group.first_seen_at = now()
