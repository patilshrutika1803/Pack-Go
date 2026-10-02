from alembic import op
import sqlalchemy as sa
revision = "20260913_000011"
down_revision = "20260913_000010"
branch_labels = depends_on = None
def upgrade():
    op.create_table("checklist_items", sa.Column("id", sa.String(36), primary_key=True), sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False), sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("assigned_to_user_id", sa.String(36), sa.ForeignKey("users.id")), sa.Column("title", sa.String(255), nullable=False), sa.Column("description", sa.Text), sa.Column("completed", sa.Boolean, nullable=False), sa.Column("completed_by_user_id", sa.String(36), sa.ForeignKey("users.id")), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
def downgrade(): op.drop_table("checklist_items")
