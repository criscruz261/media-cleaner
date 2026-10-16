"""Persistent scan totals and live group ordering."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("scan_jobs", sa.Column("total_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "duplicate_groups",
        sa.Column("updated_at", sa.String(), nullable=False, server_default="1970-01-01T00:00:00+00:00"),
    )
    op.create_index("ix_duplicate_groups_updated_at", "duplicate_groups", ["updated_at"])
    op.execute(
        "UPDATE scan_jobs SET total_bytes = COALESCE((SELECT SUM(size) FROM files WHERE files.scan_id=scan_jobs.id),0)"
    )
    op.execute(
        "UPDATE duplicate_groups SET updated_at = COALESCE((SELECT updated_at FROM scan_jobs WHERE scan_jobs.id=duplicate_groups.scan_id),updated_at)"
    )


def downgrade():
    op.drop_index("ix_duplicate_groups_updated_at", table_name="duplicate_groups")
    op.drop_column("duplicate_groups", "updated_at")
    op.drop_column("scan_jobs", "total_bytes")
