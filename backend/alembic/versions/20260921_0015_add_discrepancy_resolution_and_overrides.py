"""Add operational resolution to comparison results and generalize field overrides.

Revision ID: 20260921_0015
Revises: 20260921_0014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260921_0015"
down_revision = "20260921_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "comparison_results",
        sa.Column("resolution_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "comparison_results",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "comparison_results",
        sa.Column("acknowledged_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "comparison_results",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "comparison_results",
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "comparison_results",
        sa.Column("resolution_notes", sa.Text(), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE comparison_results "
            "SET resolution_status = 'OPEN' "
            "WHERE mismatch_found = TRUE AND comparison_state = 'COMPLETED'"
        )
    )

    op.create_check_constraint(
        "ck_comparison_resolution_status",
        "comparison_results",
        "resolution_status IS NULL OR resolution_status IN ('OPEN','ACKNOWLEDGED','RESOLVED')",
    )
    op.create_index(
        "ix_comparison_results_resolution_status",
        "comparison_results",
        ["resolution_status"],
        unique=False,
    )

    op.add_column(
        "human_review_field_overrides",
        sa.Column("comparison_result_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_field_overrides_comparison_result_id",
        "human_review_field_overrides",
        "comparison_results",
        ["comparison_result_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("human_review_field_overrides", "review_case_id", nullable=True)

    op.drop_index("uq_review_override_active_field", table_name="human_review_field_overrides")
    op.create_index(
        "uq_review_override_active_field",
        "human_review_field_overrides",
        ["review_case_id", "document_side", "field_name"],
        unique=True,
        postgresql_where=sa.text("active AND review_case_id IS NOT NULL"),
    )
    op.create_index(
        "uq_comparison_override_active_field",
        "human_review_field_overrides",
        ["comparison_result_id", "document_side", "field_name"],
        unique=True,
        postgresql_where=sa.text("active AND comparison_result_id IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_field_override_single_owner",
        "human_review_field_overrides",
        "num_nonnulls(review_case_id, comparison_result_id) = 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_field_override_single_owner", "human_review_field_overrides", type_="check")
    op.drop_index("uq_comparison_override_active_field", table_name="human_review_field_overrides")
    op.drop_index("uq_review_override_active_field", table_name="human_review_field_overrides")
    op.create_index(
        "uq_review_override_active_field",
        "human_review_field_overrides",
        ["review_case_id", "document_side", "field_name"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.alter_column("human_review_field_overrides", "review_case_id", nullable=False)
    op.drop_constraint("fk_field_overrides_comparison_result_id", "human_review_field_overrides", type_="foreignkey")
    op.drop_column("human_review_field_overrides", "comparison_result_id")

    op.drop_index("ix_comparison_results_resolution_status", table_name="comparison_results")
    op.drop_constraint("ck_comparison_resolution_status", "comparison_results", type_="check")
    op.drop_column("comparison_results", "resolution_notes")
    op.drop_column("comparison_results", "resolved_by")
    op.drop_column("comparison_results", "resolved_at")
    op.drop_column("comparison_results", "acknowledged_by")
    op.drop_column("comparison_results", "acknowledged_at")
    op.drop_column("comparison_results", "resolution_status")
