"""Keep published groups in first-seen order while matching continues."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("duplicate_groups", sa.Column("first_seen_at", sa.String(), nullable=True))
    op.create_index("ix_duplicate_groups_first_seen_at", "duplicate_groups", ["first_seen_at"])
    op.execute(
        "UPDATE duplicate_groups SET first_seen_at=updated_at WHERE member_count>1 AND review_status NOT IN ('pending', 'resolved')"
    )


def downgrade():
    op.drop_index("ix_duplicate_groups_first_seen_at", table_name="duplicate_groups")
    op.drop_column("duplicate_groups", "first_seen_at")
