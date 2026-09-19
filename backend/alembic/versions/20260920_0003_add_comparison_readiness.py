"""Add the Phase-1 post-classification readiness state.

Revision ID: 20260920_0003
Revises: 20260919_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260920_0003"
down_revision = "20260919_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("classification_results", sa.Column("comparison_readiness", sa.String(length=50), nullable=True))
    op.execute("""
        UPDATE classification_results
        SET category = CASE category
            WHEN 'DOCUMENT_COMPARISON' THEN 'document_comparison'
            WHEN 'NEW_SI_REQUEST' THEN 'new_si_request'
            WHEN 'INVOICE_QUERY' THEN 'invoice_query'
            WHEN 'GENERAL_MAIL' THEN 'general_message'
            WHEN 'SPAM' THEN 'spam'
            WHEN 'UNCERTAIN' THEN 'general_message'
            ELSE category
        END
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE classification_results
        SET category = CASE category
            WHEN 'document_comparison' THEN 'DOCUMENT_COMPARISON'
            WHEN 'new_si_request' THEN 'NEW_SI_REQUEST'
            WHEN 'invoice_query' THEN 'INVOICE_QUERY'
            WHEN 'general_message' THEN 'GENERAL_MAIL'
            WHEN 'spam' THEN 'SPAM'
            ELSE category
        END
    """)
    op.drop_column("classification_results", "comparison_readiness")
