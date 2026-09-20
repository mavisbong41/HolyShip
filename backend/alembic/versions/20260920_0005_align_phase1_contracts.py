"""Align persisted classification fields with the authoritative Phase-1 contract."""

from alembic import op
import sqlalchemy as sa


revision = "20260920_0005"
down_revision = "20260920_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "classification_results",
        sa.Column("reason_code", sa.String(length=80), nullable=True),
    )
    op.execute(
        """
        UPDATE classification_results
        SET reason_code = CASE
            WHEN resolved_at_stage = 'STAGE_1' THEN 'STAGE1_CONFIDENT'
            WHEN resolved_at_stage = 'STAGE_2' THEN 'STAGE2_RESOLVED'
            ELSE 'CLASSIFICATION_RESOLVED'
        END
        """
    )
    op.alter_column("classification_results", "reason_code", nullable=False)
    op.create_check_constraint(
        "ck_classification_category",
        "classification_results",
        "category IN ('document_comparison','new_si_request','invoice_query','general_message','spam')",
    )
    op.create_check_constraint(
        "ck_classification_confidence",
        "classification_results",
        "confidence >= 0.0 AND confidence <= 1.0",
    )
    op.create_check_constraint(
        "ck_classification_readiness",
        "classification_results",
        "comparison_readiness IS NULL OR comparison_readiness IN ('READY_FOR_COMPARISON','AWAITING_DOCUMENTS','UNRESOLVED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_classification_readiness", "classification_results", type_="check")
    op.drop_constraint("ck_classification_confidence", "classification_results", type_="check")
    op.drop_constraint("ck_classification_category", "classification_results", type_="check")
    op.drop_column("classification_results", "reason_code")
