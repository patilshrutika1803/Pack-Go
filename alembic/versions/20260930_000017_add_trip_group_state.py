"""track explicit trip group conversion state"""
from alembic import op
import sqlalchemy as sa

revision = "20260930_000017"
down_revision = "20260916_000016"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "trips",
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(sa.text("""
        UPDATE trips
        SET is_group = TRUE
        WHERE EXISTS (
            SELECT 1 FROM trip_members
            WHERE trip_members.trip_id = trips.id
              AND trip_members.status = 'active'
              AND trip_members.user_id != trips.user_id
        )
        OR EXISTS (SELECT 1 FROM trip_invitations WHERE trip_invitations.trip_id = trips.id)
        OR EXISTS (SELECT 1 FROM proposals WHERE proposals.trip_id = trips.id)
        OR EXISTS (SELECT 1 FROM decisions WHERE decisions.trip_id = trips.id)
        OR EXISTS (SELECT 1 FROM checklist_items WHERE checklist_items.trip_id = trips.id)
        OR EXISTS (SELECT 1 FROM group_messages WHERE group_messages.trip_id = trips.id)
    """))


def downgrade():
    op.drop_column("trips", "is_group")