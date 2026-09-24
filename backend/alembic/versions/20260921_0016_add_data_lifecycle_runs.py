"""Add scheduled data lifecycle run summaries.

Revision ID: 20260921_0016
Revises: 20260921_0015
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260921_0016"
down_revision = "20260921_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_lifecycle_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_lifecycle_runs_started_at", "data_lifecycle_runs", ["started_at"])
    op.create_index("ix_data_lifecycle_runs_status", "data_lifecycle_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_data_lifecycle_runs_status", table_name="data_lifecycle_runs")
    op.drop_index("ix_data_lifecycle_runs_started_at", table_name="data_lifecycle_runs")
    op.drop_table("data_lifecycle_runs")
