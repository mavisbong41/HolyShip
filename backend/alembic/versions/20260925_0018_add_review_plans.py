"""Add structured multi-action Human Review plans.

Revision ID: 20260925_0018
Revises: 20260925_0017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260925_0018"
down_revision = "20260925_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("review_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("human_review_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.String(255)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", sa.String(255)),
        sa.Column("applied_comparison_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("comparison_results.id", ondelete="SET NULL")),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT','CONFIRMED','APPLIED','APPLY_FAILED','CANCELLED')", name="ck_review_plan_status"),
    )
    op.create_index("ix_review_plans_review_case_id", "review_plans", ["review_case_id"])
    op.create_index("ix_review_plans_status", "review_plans", ["status"])
    op.create_table(
        "review_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_suggestion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_suggestions.id", ondelete="SET NULL")),
        sa.Column("document_side", sa.String(10), nullable=False),
        sa.Column("field_name", sa.String(80), nullable=False),
        sa.Column("current_value", postgresql.JSONB()),
        sa.Column("proposed_value", postgresql.JSONB(), nullable=False),
        sa.Column("human_edited_value", postgresql.JSONB()),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float()),
        sa.Column("action", sa.String(40), nullable=False, server_default="REPLACE"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PROPOSED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("document_side IN ('SI','BL')", name="ck_review_plan_item_side"),
        sa.CheckConstraint("field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')", name="ck_review_plan_item_field"),
        sa.CheckConstraint("status IN ('PROPOSED','APPROVED','EDITED','REJECTED','APPLIED')", name="ck_review_plan_item_status"),
        sa.UniqueConstraint("plan_id", "document_side", "field_name", name="uq_review_plan_item_target"),
    )
    op.create_index("ix_review_plan_items_plan_id", "review_plan_items", ["plan_id"])
    op.create_index("ix_review_plan_items_ai_suggestion_id", "review_plan_items", ["ai_suggestion_id"])


def downgrade() -> None:
    op.drop_table("review_plan_items")
    op.drop_table("review_plans")
