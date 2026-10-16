from sqlalchemy import select, func, delete
from app.database.models import File, DuplicateGroup, GroupMember
from app.retention.recommend import recommendation


def build_groups(session, scan_id: str, checkpoint=lambda: None):
    existing = select(DuplicateGroup.id).where(DuplicateGroup.scan_id == scan_id)
    session.execute(delete(GroupMember).where(GroupMember.group_id.in_(existing)))
    session.execute(delete(DuplicateGroup).where(DuplicateGroup.scan_id == scan_id))
    candidates = session.execute(
        select(File.sha256, File.size, func.count())
        .where(File.scan_id == scan_id, File.sha256.is_not(None), File.status == "ready")
        .group_by(File.sha256, File.size)
        .having(func.count() > 1)
        .execution_options(yield_per=128)
    )
    for digest, size, count in candidates:
        checkpoint()
        query = (
            select(File)
            .where(File.scan_id == scan_id, File.sha256 == digest, File.size == size, File.status == "ready")
            .order_by(File.path)
        )
        keeper, explanation = recommendation(session.scalars(query.execution_options(yield_per=128)))
        group = DuplicateGroup(
            scan_id=scan_id,
            evidence={"algorithm": "sha256-v1", "sha256": digest, "size": size},
            recommended_id=keeper,
            recommendation=explanation,
            member_count=count,
            recoverable=size * (count - 1),
        )
        session.add(group)
        session.flush()
        batch = []
        for file in session.scalars(query.execution_options(yield_per=128)):
            batch.append(
                GroupMember(
                    group_id=group.id,
                    file_id=file.id,
                    keep=keeper is None or file.id == keeper or bool(file.protected_reason),
                )
            )
            if len(batch) == 128:
                session.add_all(batch)
                session.flush()
                batch.clear()
        session.add_all(batch)
    checkpoint()
    session.commit()
