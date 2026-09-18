from alembic import op
import sqlalchemy as sa
revision = "20260913_000008"
down_revision = "20260913_000007"
branch_labels = depends_on = None
def upgrade():
    op.create_table("trip_invitations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False), sa.Column("inviter_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("invitee_user_id", sa.String(36), sa.ForeignKey("users.id")), sa.Column("invitee_email", sa.String(320)), sa.Column("token_hash", sa.String(64), unique=True, nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("accepted_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('pending', 'accepted', 'declined', 'expired', 'revoked')", name="ck_trip_invitation_status"))
    op.create_index("ix_trip_invitations_token_hash", "trip_invitations", ["token_hash"])
    op.create_index("ix_trip_invitations_invitee_email", "trip_invitations", ["invitee_email"])
def downgrade(): op.drop_table("trip_invitations")
