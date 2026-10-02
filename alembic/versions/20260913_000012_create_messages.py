from alembic import op
import sqlalchemy as sa
revision = "20260913_000012"
down_revision = "20260913_000011"
branch_labels = depends_on = None
def upgrade():
    op.create_table("group_messages", sa.Column("id", sa.String(36), primary_key=True), sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False), sa.Column("sender_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("body", sa.Text, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("edited_at", sa.DateTime(timezone=True)), sa.Column("deleted_at", sa.DateTime(timezone=True)))
def downgrade(): op.drop_table("group_messages")
