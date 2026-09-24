"""Add Outlook email lifecycle synchronisation fields.

Revision ID: 20260925_0017
Revises: 20260924_0017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260925_0017"
down_revision = "20260924_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_messages", sa.Column("lifecycle_status", sa.String(length=50), nullable=False, server_default="ACTIVE"))
    op.add_column("email_messages", sa.Column("outlook_read_state", sa.String(length=20), nullable=False, server_default="UNKNOWN"))
    op.add_column("email_messages", sa.Column("outlook_categories", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"))
    op.add_column("email_messages", sa.Column("outlook_folder_id", sa.String(length=512), nullable=True))
    op.add_column("email_messages", sa.Column("outlook_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("email_messages", sa.Column("last_outlook_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_messages", sa.Column("outlook_sync_error", sa.Text(), nullable=True))
    op.add_column("email_messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_messages", sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_email_messages_lifecycle_status", "email_messages", ["lifecycle_status"])
    op.create_index("ix_email_messages_last_outlook_sync_at", "email_messages", ["last_outlook_sync_at"])
    op.create_check_constraint(
        "ck_email_lifecycle_status",
        "email_messages",
        "lifecycle_status IN ('ACTIVE','DELETED','ARCHIVED')",
    )
    op.create_check_constraint(
        "ck_email_outlook_read_state",
        "email_messages",
        "outlook_read_state IN ('READ','UNREAD','UNKNOWN')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_email_outlook_read_state", "email_messages", type_="check")
    op.drop_constraint("ck_email_lifecycle_status", "email_messages", type_="check")
    op.drop_index("ix_email_messages_last_outlook_sync_at", table_name="email_messages")
    op.drop_index("ix_email_messages_lifecycle_status", table_name="email_messages")
    op.drop_column("email_messages", "restored_at")
    op.drop_column("email_messages", "deleted_at")
    op.drop_column("email_messages", "outlook_sync_error")
    op.drop_column("email_messages", "last_outlook_sync_at")
    op.drop_column("email_messages", "outlook_archived")
    op.drop_column("email_messages", "outlook_folder_id")
    op.drop_column("email_messages", "outlook_categories")
    op.drop_column("email_messages", "outlook_read_state")
    op.drop_column("email_messages", "lifecycle_status")
