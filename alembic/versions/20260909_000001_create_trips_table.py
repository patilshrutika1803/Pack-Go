"""create trips table

Revision ID: 20260909_000001
Revises: 
Create Date: 2026-09-09 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260909_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("total_budget", sa.Float(), nullable=False),
        sa.Column("budget_currency", sa.String(length=10), nullable=False),
        sa.Column("group_size", sa.Integer(), nullable=False),
        sa.Column("travel_style", sa.String(length=100), nullable=False),
        sa.Column("travel_dates", sa.String(length=100), nullable=True),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("things_to_avoid", sa.JSON(), nullable=False),
        sa.Column("itinerary", sa.JSON(), nullable=False),
        sa.Column("weather", sa.JSON(), nullable=True),
        sa.Column("budget_breakdown", sa.JSON(), nullable=True),
        sa.Column("critic_review", sa.JSON(), nullable=True),
        sa.Column("revision_history", sa.JSON(), nullable=False),
        sa.Column("data_freshness", sa.JSON(), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("trips")
