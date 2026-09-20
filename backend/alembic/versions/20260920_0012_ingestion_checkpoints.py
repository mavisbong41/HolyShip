"""Add durable continuous-ingestion polling checkpoints.

Revision ID: 20260920_0012
Revises: 20260920_0011
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260920_0012"
down_revision = "20260920_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("last_successful_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_external_id", sa.String(length=255), nullable=True),
        sa.Column("last_seen_content_hash", sa.String(length=64), nullable=True),
        sa.Column("poll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_ingestion_checkpoint_source_key"),
    )
    op.create_index(
        "ix_ingestion_checkpoints_source_key",
        "ingestion_checkpoints",
        ["source_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_checkpoints_source_key", table_name="ingestion_checkpoints")
    op.drop_table("ingestion_checkpoints")
