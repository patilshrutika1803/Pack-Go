from alembic import op
import sqlalchemy as sa
revision = "20260913_000010"
down_revision = "20260913_000009"
branch_labels = depends_on = None
def upgrade():
    op.create_table("decisions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False), sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id", ondelete="CASCADE"), unique=True, nullable=False), sa.Column("decided_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("result", sa.String(20), nullable=False), sa.Column("decision_type", sa.String(40), nullable=False), sa.Column("applied_action", sa.JSON), sa.Column("source_revision", sa.Integer), sa.Column("target_revision", sa.Integer), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
def downgrade(): op.drop_table("decisions")
