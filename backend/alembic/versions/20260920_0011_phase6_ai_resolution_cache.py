"""Add the Phase-6 AI resolution cache and audit table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260920_0011"
down_revision = "20260920_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("case_id", sa.String(length=255), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("source_identity", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("resolver_version", sa.String(length=80), nullable=False),
        sa.Column("prompt_schema_version", sa.String(length=80), nullable=False),
        sa.Column("request_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_reason", sa.String(length=100), nullable=False),
        sa.Column("provider_calls", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose IN ('EXTRACTION','SEMANTIC')", name="ck_ai_resolution_purpose"),
        sa.CheckConstraint(
            "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_ai_resolution_field_name",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ai_resolution_confidence"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_hash", name="uq_ai_resolution_request_hash"),
    )
    op.create_index("ix_ai_resolutions_request_hash", "ai_resolutions", ["request_hash"])
    op.create_index("ix_ai_resolutions_purpose", "ai_resolutions", ["purpose"])
    op.create_index("ix_ai_resolutions_case_id", "ai_resolutions", ["case_id"])
    op.create_index("ix_ai_resolutions_field_name", "ai_resolutions", ["field_name"])
    op.create_index("ix_ai_resolutions_validation_reason", "ai_resolutions", ["validation_reason"])


def downgrade() -> None:
    op.drop_index("ix_ai_resolutions_validation_reason", table_name="ai_resolutions")
    op.drop_index("ix_ai_resolutions_field_name", table_name="ai_resolutions")
    op.drop_index("ix_ai_resolutions_case_id", table_name="ai_resolutions")
    op.drop_index("ix_ai_resolutions_purpose", table_name="ai_resolutions")
    op.drop_index("ix_ai_resolutions_request_hash", table_name="ai_resolutions")
    op.drop_table("ai_resolutions")
