"""create batch2 document extraction tables

Revision ID: 20260919_0002
Revises: 20260919_0001
Create Date: 2026-09-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260919_0002"
down_revision: Union[str, None] = "20260919_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attachments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("format", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_email_id", "documents", ["email_id"])
    op.create_index("ix_documents_attachment_id", "documents", ["attachment_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])

    op.create_table(
        "document_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reader_used", sa.String(length=80), nullable=False),
        sa.Column("extraction_status", sa.String(length=50), nullable=False),
        sa.Column("extraction_quality", sa.Float(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("pages_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_extractions_document_id", "document_extractions", ["document_id"])

    op.create_table(
        "extracted_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extraction_method", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_extracted_fields_extraction_id", "extracted_fields", ["extraction_id"])
    op.create_index("ix_extracted_fields_field_name", "extracted_fields", ["field_name"])

    op.add_column(
        "human_review_cases",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "human_review_cases",
        sa.Column("field_name", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_human_review_cases_document_id", "human_review_cases", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_human_review_cases_document_id", table_name="human_review_cases")
    op.drop_column("human_review_cases", "field_name")
    op.drop_column("human_review_cases", "document_id")

    op.drop_index("ix_extracted_fields_field_name", table_name="extracted_fields")
    op.drop_index("ix_extracted_fields_extraction_id", table_name="extracted_fields")
    op.drop_table("extracted_fields")

    op.drop_index("ix_document_extractions_document_id", table_name="document_extractions")
    op.drop_table("document_extractions")

    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_attachment_id", table_name="documents")
    op.drop_index("ix_documents_email_id", table_name="documents")
    op.drop_table("documents")
