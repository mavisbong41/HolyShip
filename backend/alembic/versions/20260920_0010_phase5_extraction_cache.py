"""Add a durable versioned extraction-cache identity."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260920_0010"
down_revision = "20260920_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extraction_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("extractor_version", sa.String(length=80), nullable=False),
        sa.Column(
            "source_extraction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_sha256",
            "extractor_version",
            name="uq_extraction_cache_content_version",
        ),
        sa.UniqueConstraint(
            "source_extraction_id",
            name="uq_extraction_cache_source_extraction",
        ),
    )
    op.create_index(
        "ix_extraction_cache_content_sha256",
        "extraction_cache",
        ["content_sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_extraction_cache_content_sha256", table_name="extraction_cache")
    op.drop_table("extraction_cache")
