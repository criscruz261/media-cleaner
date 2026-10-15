"""Keep explicit file choices independent of provisional group rebuilds."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "file_review_choices",
        sa.Column("file_id", sa.String(), sa.ForeignKey("files.id"), primary_key=True),
        sa.Column("classification", sa.String(), primary_key=True),
        sa.Column("keep", sa.Boolean(), nullable=False),
    )
    op.execute("""
        INSERT INTO file_review_choices (file_id, classification, keep)
        SELECT m.file_id, g.classification, m.keep
        FROM group_members m JOIN duplicate_groups g ON g.id=m.group_id
        WHERE g.review_status IN ('reviewed', 'resolved')
    """)


def downgrade():
    op.drop_table("file_review_choices")
