"""add user preference choices

Revision ID: 20260910_000004
Revises: 20260910_000003
"""
from alembic import op
import sqlalchemy as sa


revision = "20260910_000004"
down_revision = "20260910_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_preferences", sa.Column("budget_preference", sa.String(length=100), nullable=True))
    op.add_column("user_preferences", sa.Column("hotel_preference", sa.String(length=100), nullable=True))
    op.add_column("user_preferences", sa.Column("food_preference", sa.String(length=100), nullable=True))
    op.add_column("user_preferences", sa.Column("preferred_destinations", sa.JSON(), nullable=True))
    op.execute("UPDATE user_preferences SET preferred_destinations = '[]' WHERE preferred_destinations IS NULL")
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.alter_column("preferred_destinations", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.drop_column("preferred_destinations")
        batch_op.drop_column("food_preference")
        batch_op.drop_column("hotel_preference")
        batch_op.drop_column("budget_preference")