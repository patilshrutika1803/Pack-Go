"""create trip memberships"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4
revision = "20260913_000007"
down_revision = "20260913_000006"
branch_labels = depends_on = None

def upgrade():
    op.create_table("trip_members", sa.Column("id", sa.String(36), primary_key=True), sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(20), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("left_at", sa.DateTime(timezone=True)), sa.Column("removed_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("trip_id", "user_id", name="uq_trip_member_user"), sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_trip_member_role"), sa.CheckConstraint("status IN ('active', 'left', 'removed')", name="ck_trip_member_status"))
    op.create_index("ix_trip_members_trip_status", "trip_members", ["trip_id", "status"])
    op.create_index("ix_trip_members_user_status", "trip_members", ["user_id", "status"])
    op.create_index("uq_trip_members_active_owner", "trip_members", ["trip_id"], unique=True, sqlite_where=sa.text("status = 'active' AND role = 'owner'"), postgresql_where=sa.text("status = 'active' AND role = 'owner'"))
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, user_id FROM trips WHERE user_id IS NOT NULL")).fetchall()
    for trip_id, user_id in rows:
        connection.execute(sa.text("INSERT INTO trip_members (id, trip_id, user_id, role, status, joined_at, updated_at) VALUES (:id, :trip_id, :user_id, 'owner', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": str(uuid4()), "trip_id": trip_id, "user_id": user_id})

def downgrade():
    op.drop_index("uq_trip_members_active_owner", table_name="trip_members")
    op.drop_table("trip_members")
