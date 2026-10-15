from sqlalchemy import select
from app.database.models import File, Fingerprint


def fingerprint_records(session, scan_id, algorithm, version):
    """Materialize bounded pages before matcher commits; do not retain streaming cursors."""
    last_path = ""
    while True:
        rows = session.execute(
            select(File.id, File.size, File.sha256, Fingerprint.value, File.path)
            .join(Fingerprint, Fingerprint.file_id == File.id)
            .where(
                File.scan_id == scan_id,
                File.status == "ready",
                File.path > last_path,
                Fingerprint.algorithm == algorithm,
                Fingerprint.version == version,
            )
            .order_by(File.path)
            .limit(128)
        ).all()
        if not rows:
            break
        for file_id, size, digest, value, path in rows:
            last_path = path
            yield file_id, size, digest, value
