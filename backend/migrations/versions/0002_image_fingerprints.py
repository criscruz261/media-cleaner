"""Index reusable identity-keyed image fingerprints."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fingerprints", sa.Column("cache_key", sa.String(), nullable=True))
    op.create_index("ix_fingerprints_cache_key", "fingerprints", ["cache_key"])


def downgrade():
    op.drop_index("ix_fingerprints_cache_key", table_name="fingerprints")
    op.drop_column("fingerprints", "cache_key")
