import re
from pathlib import Path


def recommendation(files) -> tuple[str | None, str]:
    eligible_count, eligible_id, protected_id = 0, None, None
    for file in files:
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
    return None, "No reliable original identified. All files are kept until you choose."
