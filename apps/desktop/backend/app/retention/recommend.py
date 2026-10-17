import re
from pathlib import Path


def recommendation(files) -> tuple[str | None, str]:
    eligible_count, eligible_id, protected_id = 0, None, None
    fallback = None
    for file in files:
        candidate = (file.name.casefold(), file.id)
        if fallback is None or candidate < fallback:
            fallback = candidate
        if file.protected_reason and protected_id is None:
            protected_id = file.id
        if not re.search(
            r"(?:^|[\s_-])(?:copy|duplicate)(?=$|[\s_()\d-])|\s*\(\d+\)$", Path(file.name).stem, re.IGNORECASE
        ):
            eligible_count += 1
            eligible_id = file.id
    if protected_id:
        return (
            protected_id,
            "Protected original or related asset retained; protected files cannot be cleaned up.",
        )
    if eligible_count == 1:
        return (
            eligible_id,
            "Filename lacks copy markers. Exact bytes match; filename is only an original-name heuristic.",
        )
    return (
        fallback[1] if fallback else None,
        "Exact bytes match. One file is kept by filename order; review the selection before deleting.",
    )


def initialize_exact_selections(sessions):
    """Upgrade untouched saved groups to the current one-keeper default."""
    from sqlalchemy import select
    from app.database.models import DuplicateGroup, GroupMember, File

    with sessions.begin() as session:
        groups = session.scalars(select(DuplicateGroup).where(
            DuplicateGroup.classification == "EXACT_DUPLICATE",
            DuplicateGroup.review_status == "unreviewed",
        ))
        for group in groups:
            files = session.scalars(select(File).join(GroupMember, GroupMember.file_id == File.id).where(
                GroupMember.group_id == group.id, File.status == "ready",
            )).all()
            keeper, reason = recommendation(files)
            if keeper is None:
                continue
            group.recommended_id, group.recommendation = keeper, reason
            protected = {file.id for file in files if file.protected_reason}
            for member in session.scalars(select(GroupMember).where(GroupMember.group_id == group.id)):
                member.keep = member.file_id == keeper or member.file_id in protected
