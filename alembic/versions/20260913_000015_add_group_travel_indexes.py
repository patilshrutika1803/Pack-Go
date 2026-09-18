"""complete group travel indexes and invitation target constraint"""
from alembic import op
import sqlalchemy as sa

revision = "20260913_000015"
down_revision = "20260913_000014"
branch_labels = depends_on = None


def upgrade():
    op.create_index("ix_trip_invitations_trip_status", "trip_invitations", ["trip_id", "status"])
    op.create_index("ix_trip_invitations_invitee_user_status", "trip_invitations", ["invitee_user_id", "status"])
    op.create_index("ix_trip_invitations_expires_status", "trip_invitations", ["expires_at", "status"])
    op.create_index("ix_proposals_trip_status_created", "proposals", ["trip_id", "status", "created_at"])
    op.create_index("ix_proposals_trip_deadline", "proposals", ["trip_id", "deadline"])
    op.create_index("ix_proposal_votes_choice", "proposal_votes", ["proposal_id", "choice_key"])
    op.create_index("ix_decisions_trip_created", "decisions", ["trip_id", "created_at"])
    op.create_index("ix_checklist_trip_completed_due", "checklist_items", ["trip_id", "completed", "due_at"])
    op.create_index("ix_group_messages_trip_created", "group_messages", ["trip_id", "created_at", "id"])
    op.create_index("ix_notifications_recipient_read_created", "notifications", ["recipient_user_id", "read_at", "created_at"])
    with op.batch_alter_table("trip_invitations") as batch:
        batch.create_check_constraint(
            "ck_trip_invitation_exactly_one_target",
            "(invitee_user_id IS NOT NULL AND invitee_email IS NULL) OR (invitee_user_id IS NULL AND invitee_email IS NOT NULL)",
        )


def downgrade():
    with op.batch_alter_table("trip_invitations") as batch:
        batch.drop_constraint("ck_trip_invitation_exactly_one_target", type_="check")
    op.drop_index("ix_notifications_recipient_read_created", table_name="notifications")
    op.drop_index("ix_group_messages_trip_created", table_name="group_messages")
    op.drop_index("ix_checklist_trip_completed_due", table_name="checklist_items")
    op.drop_index("ix_decisions_trip_created", table_name="decisions")
    op.drop_index("ix_proposal_votes_choice", table_name="proposal_votes")
    op.drop_index("ix_proposals_trip_deadline", table_name="proposals")
    op.drop_index("ix_proposals_trip_status_created", table_name="proposals")
    op.drop_index("ix_trip_invitations_expires_status", table_name="trip_invitations")
    op.drop_index("ix_trip_invitations_invitee_user_status", table_name="trip_invitations")
    op.drop_index("ix_trip_invitations_trip_status", table_name="trip_invitations")
