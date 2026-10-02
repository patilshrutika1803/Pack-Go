from alembic import op
import sqlalchemy as sa

revision = "20260913_000014"
down_revision = "20260913_000013"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("payload_history", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("decisions") as batch:
        batch.add_column(sa.Column("vote_counts", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("proposal_snapshot", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    with op.batch_alter_table("decisions") as batch:
        batch.drop_column("proposal_snapshot")
        batch.drop_column("vote_counts")
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("payload_history")