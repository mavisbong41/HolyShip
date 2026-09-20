"""Persist Phase-2 attachment materialization and document-role outcomes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260920_0006"
down_revision = "20260920_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attachments", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.add_column("attachments", sa.Column("retrieval_status", sa.String(length=50), nullable=True))
    op.add_column("attachments", sa.Column("retrieval_reason_code", sa.String(length=80), nullable=True))
    op.execute("UPDATE attachments SET retrieval_status = 'NOT_RETRIEVED'")
    op.alter_column("attachments", "retrieval_status", nullable=False)
    op.create_index("ix_attachments_content_sha256", "attachments", ["content_sha256"])
    op.create_check_constraint(
        "ck_attachment_retrieval_status",
        "attachments",
        "retrieval_status IN ('NOT_RETRIEVED','MATERIALIZED','FAILED')",
    )

    op.add_column("documents", sa.Column("routing_outcome", sa.String(length=50), nullable=True))
    op.add_column("documents", sa.Column("role_confidence", sa.Float(), nullable=True))
    op.add_column("documents", sa.Column("role_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("documents", sa.Column("validation_outcome", sa.String(length=50), nullable=True))
    op.add_column("documents", sa.Column("parse_duration_ms", sa.Float(), nullable=True))
    op.execute(
        "UPDATE documents SET routing_outcome = 'LEGACY_UNCLASSIFIED', "
        "role_confidence = 0.0, role_evidence = '{}'::jsonb, validation_outcome = 'INCONCLUSIVE'"
    )
    op.alter_column("documents", "routing_outcome", nullable=False)
    op.alter_column("documents", "role_confidence", nullable=False)
    op.alter_column("documents", "role_evidence", nullable=False)
    op.alter_column("documents", "validation_outcome", nullable=False)
    op.create_check_constraint(
        "ck_document_routing_outcome",
        "documents",
        "routing_outcome IN ('SI_FOUND','BL_FOUND','MULTIPLE_CANDIDATES','MISSING_REQUIRED_ATTACHMENT','UNSUPPORTED_ATTACHMENT','CORRUPTED_ATTACHMENT','UNREADABLE_ATTACHMENT','WRONG_DOCUMENT_TYPE','ROLE_INCONCLUSIVE','LEGACY_UNCLASSIFIED')",
    )
    op.create_check_constraint(
        "ck_document_validation_outcome",
        "documents",
        "validation_outcome IN ('VALID','WRONG_DOCUMENT_TYPE','INCONCLUSIVE')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_validation_outcome", "documents", type_="check")
    op.drop_constraint("ck_document_routing_outcome", "documents", type_="check")
    op.drop_column("documents", "parse_duration_ms")
    op.drop_column("documents", "validation_outcome")
    op.drop_column("documents", "role_evidence")
    op.drop_column("documents", "role_confidence")
    op.drop_column("documents", "routing_outcome")
    op.drop_constraint("ck_attachment_retrieval_status", "attachments", type_="check")
    op.drop_index("ix_attachments_content_sha256", table_name="attachments")
    op.drop_column("attachments", "retrieval_reason_code")
    op.drop_column("attachments", "retrieval_status")
    op.drop_column("attachments", "content_sha256")
