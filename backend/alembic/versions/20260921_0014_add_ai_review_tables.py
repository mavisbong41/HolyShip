"""Add AI Review suggestions and extend Human Review audit actions.

Revision ID: 20260921_0014
Revises: 20260921_0013
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260921_0014"
down_revision = "20260921_0013"
branch_labels = None
depends_on = None


_FIELDS = (
    "'shipper','consignee','notify_party','port_of_loading',"
    "'port_of_discharge','container_count','gross_weight_kg'"
)

_OLD_EVENT_ACTIONS = (
    "'CASE_CREATED','CASE_OPENED','CASE_CLAIMED','FIELD_OVERRIDE_ADDED',"
    "'FIELD_OVERRIDE_REPLACED','RESOLVE_REQUESTED','RECOMPARISON_COMPLETED',"
    "'CASE_RESOLVED','CASE_DISMISSED'"
)

_NEW_EVENT_ACTIONS = (
    "'CASE_CREATED','CASE_OPENED','CASE_CLAIMED','FIELD_OVERRIDE_ADDED',"
    "'FIELD_OVERRIDE_REPLACED','RESOLVE_REQUESTED','RECOMPARISON_COMPLETED',"
    "'CASE_RESOLVED','CASE_DISMISSED','AI_ASSISTANT_ASKED','AI_SUGGESTION_CREATED',"
    "'AI_SUGGESTION_ACCEPTED','AI_SUGGESTION_EDITED','AI_SUGGESTION_DISMISSED'"
)


def upgrade() -> None:
    op.create_table(
        "ai_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("human_review_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("document_side", sa.String(length=10), nullable=True),
        sa.Column("field", sa.String(length=80), nullable=True),
        sa.Column("current_value", sa.Text(), nullable=True),
        sa.Column("suggested_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("provider_name", sa.String(length=80), server_default="disabled", nullable=False),
        sa.Column("provider_model", sa.String(length=160), server_default="none", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "mode IN ('EXPLANATION_ONLY','ACTIONABLE_SUGGESTION','INSUFFICIENT_EVIDENCE')",
            name="ck_ai_suggestion_mode",
        ),
        sa.CheckConstraint(
            "document_side IS NULL OR document_side IN ('SI','BL')",
            name="ck_ai_suggestion_side",
        ),
        sa.CheckConstraint(
            f"field IS NULL OR field IN ({_FIELDS})",
            name="ck_ai_suggestion_field",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','ACCEPTED','EDITED_APPLIED','DISMISSED')",
            name="ck_ai_suggestion_status",
        ),
        sa.ForeignKeyConstraint(
            ["human_review_case_id"],
            ["human_review_cases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_suggestions_human_review_case_id",
        "ai_suggestions",
        ["human_review_case_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_suggestions_created_at",
        "ai_suggestions",
        ["created_at"],
        unique=False,
    )

    op.add_column(
        "human_review_field_overrides",
        sa.Column("ai_suggestion_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_human_review_field_overrides_ai_suggestion_id",
        "human_review_field_overrides",
        "ai_suggestions",
        ["ai_suggestion_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_human_review_field_overrides_ai_suggestion_id",
        "human_review_field_overrides",
        ["ai_suggestion_id"],
        unique=False,
    )

    op.drop_constraint("ck_human_review_event_action", "human_review_events", type_="check")
    op.create_check_constraint(
        "ck_human_review_event_action",
        "human_review_events",
        f"action IN ({_NEW_EVENT_ACTIONS})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_human_review_event_action", "human_review_events", type_="check")
    op.create_check_constraint(
        "ck_human_review_event_action",
        "human_review_events",
        f"action IN ({_OLD_EVENT_ACTIONS})",
    )

    op.drop_constraint(
        "fk_human_review_field_overrides_ai_suggestion_id",
        "human_review_field_overrides",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_human_review_field_overrides_ai_suggestion_id",
        table_name="human_review_field_overrides",
    )
    op.drop_column("human_review_field_overrides", "ai_suggestion_id")

    op.drop_index("ix_ai_suggestions_created_at", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_human_review_case_id", table_name="ai_suggestions")
    op.drop_table("ai_suggestions")
