"""create trip expense ledger"""
from alembic import op
import sqlalchemy as sa

revision = "20260930_000018"
down_revision = "20260930_000017"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payer_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("split_type", sa.String(10), nullable=False, server_default="equal"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint("split_type IN ('equal', 'custom')", name="ck_expenses_split_type"),
        sa.CheckConstraint("category IN ('accommodation', 'food', 'transport', 'activities', 'shopping', 'other')", name="ck_expenses_category"),
    )
    op.create_index("ix_expenses_trip_date", "expenses", ["trip_id", "expense_date", "id"])
    op.create_index("ix_expenses_trip_category", "expenses", ["trip_id", "category"])
    op.create_table(
        "expense_shares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_share_user"),
        sa.CheckConstraint("amount >= 0", name="ck_expense_share_amount_nonnegative"),
    )
    op.create_index("ix_expense_shares_user", "expense_shares", ["user_id"])


def downgrade():
    op.drop_index("ix_expense_shares_user", table_name="expense_shares")
    op.drop_table("expense_shares")
    op.drop_index("ix_expenses_trip_category", table_name="expenses")
    op.drop_index("ix_expenses_trip_date", table_name="expenses")
    op.drop_table("expenses")
