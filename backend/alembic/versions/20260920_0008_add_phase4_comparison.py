"""Add Phase-4 comparison result and per-field evidence persistence.

Revision ID: 20260920_0008
Revises: 20260920_0007
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260920_0008"
down_revision = "20260920_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comparison_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "email_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "si_extraction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bl_extraction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("comparison_version", sa.String(length=80), nullable=False),
        sa.Column("comparison_state", sa.String(length=50), nullable=False),
        sa.Column("mismatch_found", sa.Boolean(), nullable=False),
        sa.Column("all_fields_definite", sa.Boolean(), nullable=False),
        sa.Column(
            "mismatched_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "unresolved_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "email_id",
            "si_extraction_id",
            "bl_extraction_id",
            "comparison_version",
            name="uq_comparison_identity_version",
        ),
        sa.CheckConstraint(
            "comparison_state IN ('COMPLETED','BLOCKED')",
            name="ck_comparison_result_state",
        ),
    )
    op.create_index("ix_comparison_results_email_id", "comparison_results", ["email_id"])
    op.create_index(
        "ix_comparison_results_si_extraction_id",
        "comparison_results",
        ["si_extraction_id"],
    )
    op.create_index(
        "ix_comparison_results_bl_extraction_id",
        "comparison_results",
        ["bl_extraction_id"],
    )
    op.create_index(
        "ix_comparison_results_comparison_state",
        "comparison_results",
        ["comparison_state"],
    )

    op.create_table(
        "field_comparisons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "comparison_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comparison_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "si_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bl_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("si_raw_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bl_raw_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("si_canonical_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bl_canonical_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("si_normalized_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bl_normalized_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("comparison_layer", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "comparison_result_id",
            "field_name",
            name="uq_field_comparison_result_name",
        ),
        sa.CheckConstraint(
            "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_field_comparison_name",
        ),
        sa.CheckConstraint(
            "status IN ('MATCH','MISMATCH','UNRESOLVED')",
            name="ck_field_comparison_status",
        ),
        sa.CheckConstraint(
            "comparison_layer IN ('PRECONDITION','L0','L1','L2')",
            name="ck_field_comparison_layer",
        ),
    )
    op.create_index(
        "ix_field_comparisons_comparison_result_id",
        "field_comparisons",
        ["comparison_result_id"],
    )
    op.create_index("ix_field_comparisons_field_name", "field_comparisons", ["field_name"])
    op.create_index("ix_field_comparisons_status", "field_comparisons", ["status"])


def downgrade() -> None:
    op.drop_index("ix_field_comparisons_status", table_name="field_comparisons")
    op.drop_index("ix_field_comparisons_field_name", table_name="field_comparisons")
    op.drop_index(
        "ix_field_comparisons_comparison_result_id",
        table_name="field_comparisons",
    )
    op.drop_table("field_comparisons")
    op.drop_index("ix_comparison_results_comparison_state", table_name="comparison_results")
    op.drop_index("ix_comparison_results_bl_extraction_id", table_name="comparison_results")
    op.drop_index("ix_comparison_results_si_extraction_id", table_name="comparison_results")
    op.drop_index("ix_comparison_results_email_id", table_name="comparison_results")
    op.drop_table("comparison_results")
