"""create knowledge sources table

Revision ID: 20260910_000005
Revises: 20260910_000004
"""
from alembic import op
import sqlalchemy as sa


revision = "20260910_000005"
down_revision = "20260910_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index("ix_knowledge_sources_document_id", "knowledge_sources", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_sources_document_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")