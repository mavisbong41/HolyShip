"""Add durable Phase-5 identities for duplicate protection and resume."""

from alembic import op
import sqlalchemy as sa


revision = "20260920_0009"
down_revision = "20260920_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processing_jobs",
        sa.Column("source_content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_processing_jobs_source_content_hash",
        "processing_jobs",
        ["source_content_hash"],
    )
    op.create_unique_constraint(
        "uq_processing_job_email_type_content",
        "processing_jobs",
        ["email_id", "job_type", "source_content_hash"],
    )

    op.add_column(
        "classification_results",
        sa.Column("source_content_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_classification_results_source_content_hash",
        "classification_results",
        ["source_content_hash"],
    )
    op.create_unique_constraint(
        "uq_classification_email_content_version",
        "classification_results",
        ["email_id", "source_content_hash", "classifier_version"],
    )

    op.create_unique_constraint(
        "uq_attachment_email_source_reference",
        "attachments",
        ["email_id", "source_reference"],
    )

    op.add_column(
        "documents",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_documents_content_sha256", "documents", ["content_sha256"])
    op.create_unique_constraint(
        "uq_document_attachment_content",
        "documents",
        ["attachment_id", "content_sha256"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_document_attachment_content", "documents", type_="unique")
    op.drop_index("ix_documents_content_sha256", table_name="documents")
    op.drop_column("documents", "content_sha256")
    op.drop_constraint(
        "uq_attachment_email_source_reference",
        "attachments",
        type_="unique",
    )
    op.drop_constraint(
        "uq_classification_email_content_version",
        "classification_results",
        type_="unique",
    )
    op.drop_index(
        "ix_classification_results_source_content_hash",
        table_name="classification_results",
    )
    op.drop_column("classification_results", "source_content_hash")
    op.drop_constraint(
        "uq_processing_job_email_type_content",
        "processing_jobs",
        type_="unique",
    )
    op.drop_index(
        "ix_processing_jobs_source_content_hash",
        table_name="processing_jobs",
    )
    op.drop_column("processing_jobs", "attempt_count")
    op.drop_column("processing_jobs", "source_content_hash")
