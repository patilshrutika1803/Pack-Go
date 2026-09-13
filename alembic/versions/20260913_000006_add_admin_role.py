"""add backend-enforced admin role

Revision ID: 20260913_000006
Revises: 20260910_000005
"""
from alembic import op
import sqlalchemy as sa


revision = "20260913_000006"
down_revision = "20260910_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "is_admin",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    op.drop_column("users", "is_admin")