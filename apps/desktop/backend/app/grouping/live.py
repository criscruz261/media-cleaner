"""Single-coordinator incremental match publication; all records persist in SQLite."""

from sqlalchemy import select, delete
from app.database.models import (
    File,
    DuplicateGroup,
    GroupMember,
    Fingerprint,
    ScanJob,
    SimilarityMatch,
    FileReviewChoice,
    now,
)
from app.retention.recommend import recommendation
from app.similarity.images import image_matcher, ALGORITHM, VERSION
from app.similarity.temporal import ALGORITHM as TEMPORAL, VERSION as TEMPORAL_VERSION
from app.similarity.sequences import sequence_matcher


class LiveMatcher:
    def __init__(self, sessions, scan_id, options, checkpoint):
        self.session = sessions()
        self.scan_id = scan_id
        self.checkpoint = checkpoint
        self.exact = {}
        self.restored_members = set()
        self.seen = set()
        # Keep explicit choices across resume and index rebuilds after live cleanup.
        self.saved_choices = {
            (choice.file_id, choice.classification): choice.keep
            for choice in self.session.scalars(
                select(FileReviewChoice).join(File).where(File.scan_id == scan_id)
            )
        }
        # Group rows are rebuilt on resume/live cleanup. Preserve the explicit
        # keep-none action alongside file choices, rather than losing its flag.
        self.keep_none_files = set()
        for group in self.session.scalars(select(DuplicateGroup).where(
            DuplicateGroup.scan_id == scan_id, DuplicateGroup.review_status == "reviewed",
        )):
            if group.evidence.get("allow_keep_none"):
                self.keep_none_files.update(
                    (member.file_id, group.classification)
                    for member in self.session.scalars(
                        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.keep.is_(False))
                    )
                )
        groups = select(DuplicateGroup.id).where(DuplicateGroup.scan_id == scan_id)
        self.session.execute(delete(GroupMember).where(GroupMember.group_id.in_(groups)))
        self.session.execute(delete(DuplicateGroup).where(DuplicateGroup.scan_id == scan_id))
        files = select(File.id).where(File.scan_id == scan_id)
        self.session.execute(delete(SimilarityMatch).where(SimilarityMatch.left_id.in_(files)))
        self.session.commit()
        self.matchers = {}
        if options["mode"] == "similar":
            for algorithm, version, factory in [
                (ALGORITHM, VERSION, image_matcher),
                (TEMPORAL, TEMPORAL_VERSION, sequence_matcher),
            ]:
                matcher = factory(self.session, scan_id, options.get("sensitivity", "balanced"), checkpoint)
                next(matcher)
                self.matchers[(algorithm, version)] = matcher

    def add(self, file_id):
        self.checkpoint()
        self.session.expire_all()
        if file_id in self.seen:
            return
        self.seen.add(file_id)
        file = self.session.get(File, file_id)
        self.session.refresh(file)
        for choice in self.session.scalars(
            select(FileReviewChoice).where(FileReviewChoice.file_id == file_id)
        ):
            self.saved_choices[(file_id, choice.classification)] = choice.keep
        if file.status != "ready":
            self.session.commit()
            return
        if file.sha256:
            key = (file.size, file.sha256)
            cluster = self.exact.get(key)
            if cluster is None:
                self.exact[key] = {"first": file.id, "group": None, "count": 1}
            else:
                cluster["count"] += 1
                if cluster["group"] is None:
                    group = DuplicateGroup(
                        scan_id=self.scan_id,
                        classification="EXACT_DUPLICATE",
                        evidence={"algorithm": "sha256-v1", "sha256": file.sha256, "size": file.size},
                        recommendation="Exact contents match. Retention suggestions are finalized after scanning.",
                        member_count=2,
                        recoverable=file.size,
                    )
                    self.session.add(group)
                    self.session.flush()
                    cluster["group"] = group.id
                    self.session.add(GroupMember(group_id=group.id, file_id=cluster["first"], keep=True))
                group = self.session.get(DuplicateGroup, cluster["group"])
                group.member_count = cluster["count"]
                group.recoverable = file.size * (cluster["count"] - 1)
                group.updated_at = now()
                self.session.add(GroupMember(group_id=group.id, file_id=file.id, keep=True))
                self.session.flush()
                if group.review_status != "reviewed" and not any(
                    (member.file_id, group.classification) in self.saved_choices
                    for member in self.session.scalars(
                        select(GroupMember).where(GroupMember.group_id == group.id)
                    )
                ):
                    keeper, reason = recommendation(self.session.scalars(
                        select(File).join(GroupMember, GroupMember.file_id == File.id)
                        .where(GroupMember.group_id == group.id)
                    ))
                    group.recommended_id, group.recommendation = keeper, reason
                    for member in self.session.scalars(
                        select(GroupMember).where(GroupMember.group_id == group.id)
                    ):
                        item = self.session.get(File, member.file_id)
                        member.keep = member.file_id == keeper or bool(item.protected_reason)

        self.session.get(ScanJob, self.scan_id).updated_at = now()
        self.session.commit()
        for (algorithm, version), matcher in self.matchers.items():
            descriptor = self.session.scalar(
                select(Fingerprint).where(
                    Fingerprint.file_id == file.id,
                    Fingerprint.algorithm == algorithm,
                    Fingerprint.version == version,
                )
            )
            if descriptor:
                record = (file.id, file.size, file.sha256, descriptor.value)
                matcher.send(record)
            else:
                self.session.commit()

        # Reapply persisted choices to rebuilt groups; newly discovered files stay kept.
        for group in self.session.scalars(
            select(DuplicateGroup)
            .join(GroupMember)
            .where(GroupMember.file_id == file_id, DuplicateGroup.scan_id == self.scan_id)
        ).all():
            if not self.saved_choices:
                continue
            restored = False
            for member in self.session.scalars(select(GroupMember).where(GroupMember.group_id == group.id)):
                key = (member.file_id, group.classification)
                if key in self.saved_choices:
                    restore_key = (group.id, member.file_id)
                    if restore_key not in self.restored_members:
                        member.keep = self.saved_choices[key]
                        self.restored_members.add(restore_key)
                    restored = True
            if restored and group.review_status != "pending":
                group.review_status = "reviewed"
                members = self.session.scalars(
                    select(GroupMember).where(GroupMember.group_id == group.id)
                ).all()
                if members and all(
                    not member.keep and (member.file_id, group.classification) in self.keep_none_files
                    for member in members
                ):
                    group.evidence = dict(group.evidence, allow_keep_none=True)
        self.session.commit()

    def finish(self):
        self.session.expire_all()
        for matcher in self.matchers.values():
            try:
                matcher.send(None)
            except StopIteration:
                pass
        # Apply original-name suggestions only after exact groups are complete.
        for cluster in self.exact.values():
            self.checkpoint()
            if not cluster["group"]:
                continue
            group = self.session.get(DuplicateGroup, cluster["group"])
            self.session.refresh(group)
            query = (
                select(File)
                .join(GroupMember, GroupMember.file_id == File.id)
                .where(GroupMember.group_id == group.id, File.status == "ready")
            )
            keeper, reason = recommendation(self.session.scalars(query.execution_options(yield_per=128)))
            group.recommended_id, group.recommendation = keeper, reason
            if group.review_status == "reviewed":
                self.session.commit()
                continue
            members = self.session.scalars(select(GroupMember).where(GroupMember.group_id == group.id))
            for member in members:
                file = self.session.get(File, member.file_id)
                member.keep = keeper is None or file.id == keeper or bool(file.protected_reason)
            self.session.commit()

    def close(self):
        for matcher in self.matchers.values():
            matcher.close()
        self.session.close()
