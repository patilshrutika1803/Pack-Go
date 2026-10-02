"""align database indexes and trip ownership foreign key"""
from alembic import op


revision = "20261001_000020"
down_revision = "20261001_000019"
branch_labels = depends_on = None


def upgrade():
    for table_name, index_name in (
        ("users", "ix_users_email"),
        ("user_preferences", "ix_user_preferences_user_id"),
        ("refresh_tokens", "ix_refresh_tokens_token_hash"),
        ("verification_tokens", "ix_verification_tokens_token_hash"),
        ("password_reset_tokens", "ix_password_reset_tokens_token_hash"),
        ("knowledge_sources", "ix_knowledge_sources_document_id"),
        ("trip_invitations", "ix_trip_invitations_token_hash"),
    ):
        op.drop_index(index_name, table_name=table_name)
        column_name = {
            "users": "email",
            "user_preferences": "user_id",
            "refresh_tokens": "token_hash",
            "verification_tokens": "token_hash",
            "password_reset_tokens": "token_hash",
            "knowledge_sources": "document_id",
            "trip_invitations": "token_hash",
        }[table_name]
        op.create_index(index_name, table_name, [column_name], unique=True)

    with op.batch_alter_table("trips") as batch_op:
        batch_op.create_foreign_key("fk_trips_user_id_users", "users", ["user_id"], ["id"])


def downgrade():
    with op.batch_alter_table("trips") as batch_op:
        batch_op.drop_constraint("fk_trips_user_id_users", type_="foreignkey")

    for table_name, index_name, column_name in (
        ("users", "ix_users_email", "email"),
        ("user_preferences", "ix_user_preferences_user_id", "user_id"),
        ("refresh_tokens", "ix_refresh_tokens_token_hash", "token_hash"),
        ("verification_tokens", "ix_verification_tokens_token_hash", "token_hash"),
        ("password_reset_tokens", "ix_password_reset_tokens_token_hash", "token_hash"),
        ("knowledge_sources", "ix_knowledge_sources_document_id", "document_id"),
        ("trip_invitations", "ix_trip_invitations_token_hash", "token_hash"),
    ):
        op.drop_index(index_name, table_name=table_name)
        op.create_index(index_name, table_name, [column_name], unique=False)