"""create trip journal entries"""
from alembic import op
import sqlalchemy as sa

revision = "20261001_000019"
down_revision = "20260930_000018"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("media_references", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_journal_entries_trip_occurred", "journal_entries", ["trip_id", "occurred_at", "id"])


def downgrade():
    op.drop_index("ix_journal_entries_trip_occurred", table_name="journal_entries")
    op.drop_table("journal_entries")