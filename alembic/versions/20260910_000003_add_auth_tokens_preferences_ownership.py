"""add auth tokens preferences and trip ownership

Revision ID: 20260910_000003
Revises: 20260909_000002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_000003"
down_revision = "20260909_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("updated_at", nullable=False)

    op.add_column("trips", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_index("ix_trips_user_id", "trips", ["user_id"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("travel_style", sa.String(length=100), nullable=True),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("things_to_avoid", sa.JSON(), nullable=False),
        sa.Column("preferred_budget_min", sa.Float(), nullable=True),
        sa.Column("preferred_budget_max", sa.Float(), nullable=True),
        sa.Column("preferred_currency", sa.String(length=10), nullable=False),
        sa.Column("preferred_trip_duration", sa.Integer(), nullable=True),
        sa.Column("is_domestic", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=False)

    for table in ("refresh_tokens", "verification_tokens", "password_reset_tokens"):
        columns = [
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        ]
        if table == "refresh_tokens":
            columns.extend([sa.Column("revoked_at", sa.DateTime(), nullable=True), sa.Column("replaced_by", sa.String(length=36), nullable=True)])
        else:
            columns.append(sa.Column("used_at", sa.DateTime(), nullable=True))
        op.create_table(table, *columns, sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"))
        op.create_index(f"ix_{table}_user_id", table, ["user_id"], unique=False)
        op.create_index(f"ix_{table}_token_hash", table, ["token_hash"], unique=False)


def downgrade() -> None:
    for table in ("password_reset_tokens", "verification_tokens", "refresh_tokens"):
        op.drop_table(table)
    op.drop_table("user_preferences")
    op.drop_index("ix_trips_user_id", table_name="trips")
    op.drop_column("trips", "user_id")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("updated_at")