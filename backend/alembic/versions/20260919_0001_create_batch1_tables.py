"""create batch1 persistence tables

Revision ID: 20260919_0001
Revises:
Create Date: 2026-09-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260919_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("sender", sa.String(length=512), nullable=True),
        sa.Column("recipients", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_type", "external_message_id", name="uq_email_source_external_id"),
    )
    op.create_index("ix_email_messages_external_message_id", "email_messages", ["external_message_id"])
    op.create_index("ix_email_messages_source_type", "email_messages", ["source_type"])
    op.create_index("ix_email_messages_content_hash", "email_messages", ["content_hash"])

    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("external_attachment_id", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attachments_email_id", "attachments", ["email_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_processing_jobs_email_id", "processing_jobs", ["email_id"])

    op.create_table(
        "classification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("candidate_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conflict_detected", sa.Boolean(), nullable=False),
        sa.Column("resolved_at_stage", sa.String(length=50), nullable=False),
        sa.Column("classifier_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_classification_results_email_id", "classification_results", ["email_id"])

    op.create_table(
        "human_review_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("candidate_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_human_review_cases_email_id", "human_review_cases", ["email_id"])


def downgrade() -> None:
    op.drop_index("ix_human_review_cases_email_id", table_name="human_review_cases")
    op.drop_table("human_review_cases")
    op.drop_index("ix_classification_results_email_id", table_name="classification_results")
    op.drop_table("classification_results")
    op.drop_index("ix_processing_jobs_email_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_attachments_email_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_email_messages_content_hash", table_name="email_messages")
    op.drop_index("ix_email_messages_source_type", table_name="email_messages")
    op.drop_index("ix_email_messages_external_message_id", table_name="email_messages")
    op.drop_table("email_messages")

