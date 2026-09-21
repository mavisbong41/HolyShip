"""Activate the auditable Human Review workflow.

Revision ID: 20260921_0013
Revises: 20260920_0012
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260921_0013"
down_revision = "20260920_0012"
branch_labels = None
depends_on = None


_FIELDS = (
    "'shipper','consignee','notify_party','port_of_loading',"
    "'port_of_discharge','container_count','gross_weight_kg'"
)


def upgrade() -> None:
    op.add_column(
        "human_review_cases",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("resolution", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("case_origin", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("workflow_identity", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("source_comparison_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_human_review_cases_source_comparison_id",
        "human_review_cases",
        ["source_comparison_id"],
    )

    # Existing rows are intentionally retained and labelled as legacy rather
    # than being presented as cases created by the active workflow.
    op.execute(
        sa.text(
            "UPDATE human_review_cases "
            "SET updated_at = created_at, case_origin = 'LEGACY', "
            "workflow_identity = 'legacy:' || id::text"
        )
    )
    op.alter_column("human_review_cases", "updated_at", nullable=False)
    op.alter_column("human_review_cases", "case_origin", nullable=False, server_default="ACTIVE")
    op.alter_column("human_review_cases", "workflow_identity", nullable=False)
    op.create_check_constraint(
        "ck_human_review_status",
        "human_review_cases",
        "status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED')",
    )
    op.create_check_constraint(
        "ck_human_review_case_origin",
        "human_review_cases",
        "case_origin IN ('LEGACY','ACTIVE')",
    )
    op.create_index(
        "uq_human_review_active_identity",
        "human_review_cases",
        ["email_id", "reason_code", "workflow_identity"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN','IN_REVIEW')"),
    )

    op.add_column(
        "comparison_results",
        sa.Column("review_case_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "comparison_results",
        sa.Column("supersedes_comparison_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_comparison_review_case",
        "comparison_results",
        "human_review_cases",
        ["review_case_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_comparison_supersedes",
        "comparison_results",
        "comparison_results",
        ["supersedes_comparison_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_comparison_results_review_case_id", "comparison_results", ["review_case_id"])
    op.create_index(
        "ix_comparison_results_supersedes_comparison_id",
        "comparison_results",
        ["supersedes_comparison_id"],
    )

    op.create_table(
        "human_review_field_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_review_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_side", sa.String(length=10), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column(
            "original_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fields.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("corrected_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "corrected_canonical_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "supersedes_override_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_review_field_overrides.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("document_side IN ('SI','BL')", name="ck_review_override_side"),
        sa.CheckConstraint(f"field_name IN ({_FIELDS})", name="ck_review_override_field_name"),
    )
    op.create_index(
        "ix_review_field_overrides_review_case_id",
        "human_review_field_overrides",
        ["review_case_id"],
    )
    op.create_index(
        "ix_review_field_overrides_original_field_id",
        "human_review_field_overrides",
        ["original_field_id"],
    )
    op.create_index(
        "uq_review_override_active_field",
        "human_review_field_overrides",
        ["review_case_id", "document_side", "field_name"],
        unique=True,
        postgresql_where=sa.text("active"),
    )

    op.create_table(
        "human_review_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_review_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('CASE_CREATED','CASE_OPENED','CASE_CLAIMED','FIELD_OVERRIDE_ADDED','FIELD_OVERRIDE_REPLACED','RESOLVE_REQUESTED','RECOMPARISON_COMPLETED','CASE_RESOLVED','CASE_DISMISSED')",
            name="ck_human_review_event_action",
        ),
    )
    op.create_index(
        "ix_human_review_events_review_case_id",
        "human_review_events",
        ["review_case_id"],
    )
    op.create_index("ix_human_review_events_action", "human_review_events", ["action"])
    op.create_index("ix_human_review_events_created_at", "human_review_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("human_review_events")
    op.drop_table("human_review_field_overrides")
    op.drop_index("ix_comparison_results_supersedes_comparison_id", table_name="comparison_results")
    op.drop_index("ix_comparison_results_review_case_id", table_name="comparison_results")
    op.drop_constraint("fk_comparison_supersedes", "comparison_results", type_="foreignkey")
    op.drop_constraint("fk_comparison_review_case", "comparison_results", type_="foreignkey")
    op.drop_column("comparison_results", "supersedes_comparison_id")
    op.drop_column("comparison_results", "review_case_id")
    op.drop_index("uq_human_review_active_identity", table_name="human_review_cases")
    op.drop_constraint("ck_human_review_case_origin", "human_review_cases", type_="check")
    op.drop_constraint("ck_human_review_status", "human_review_cases", type_="check")
    op.drop_index("ix_human_review_cases_source_comparison_id", table_name="human_review_cases")
    op.drop_column("human_review_cases", "source_comparison_id")
    op.drop_column("human_review_cases", "workflow_identity")
    op.drop_column("human_review_cases", "case_origin")
    op.drop_column("human_review_cases", "notes")
    op.drop_column("human_review_cases", "resolution")
    op.drop_column("human_review_cases", "reviewer_name")
    op.drop_column("human_review_cases", "resolved_at")
    op.drop_column("human_review_cases", "updated_at")
