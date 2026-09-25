"""Add durable provider cursor and checkpoint metadata.

Revision ID: 20260925_0019
Revises: 20260925_0018
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260925_0019"
down_revision = "20260925_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_checkpoints", sa.Column("cursor_value", sa.Text()))
    op.add_column("ingestion_checkpoints", sa.Column("cursor_updated_at", sa.DateTime(timezone=True)))
    op.add_column(
        "ingestion_checkpoints",
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("ingestion_checkpoints", "metadata_json")
    op.drop_column("ingestion_checkpoints", "cursor_updated_at")
    op.drop_column("ingestion_checkpoints", "cursor_value")
