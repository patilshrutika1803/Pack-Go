from alembic import op
import sqlalchemy as sa
revision = "20260913_000013"
down_revision = "20260913_000012"
branch_labels = depends_on = None
def upgrade():
    op.create_table("notifications", sa.Column("id", sa.String(36), primary_key=True), sa.Column("recipient_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE")), sa.Column("event_type", sa.String(60), nullable=False), sa.Column("payload", sa.JSON, nullable=False), sa.Column("read_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
def downgrade(): op.drop_table("notifications")
