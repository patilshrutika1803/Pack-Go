"""allow untargeted invitation links"""
from alembic import op

revision = "20260916_000016"
down_revision = "20260913_000015"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("trip_invitations") as batch:
        batch.drop_constraint("ck_trip_invitation_exactly_one_target", type_="check")


def downgrade():
    with op.batch_alter_table("trip_invitations") as batch:
        batch.create_check_constraint(
            "ck_trip_invitation_exactly_one_target",
            "(invitee_user_id IS NOT NULL AND invitee_email IS NULL) OR (invitee_user_id IS NULL AND invitee_email IS NOT NULL)",
        )