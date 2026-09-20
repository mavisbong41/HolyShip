"""Add authoritative Phase-1 processing state and immutable events."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260920_0004"
down_revision = "20260920_0003"
branch_labels = None
depends_on = None

_STATUSES = "'NEW','QUEUED','CLASSIFYING','CLASSIFIED','AWAITING_DOCUMENTS','RETRIEVING_ATTACHMENTS','EXTRACTING','COMPARING','COMPLETED','BLOCKED','FAILED'"

def upgrade():
    op.add_column("email_messages", sa.Column("processing_status", sa.String(50), nullable=True))
    op.execute("""UPDATE email_messages SET processing_status = CASE WHEN id IN (SELECT email_id FROM classification_results WHERE category='document_comparison' AND comparison_readiness='AWAITING_DOCUMENTS') THEN 'AWAITING_DOCUMENTS' WHEN id IN (SELECT email_id FROM classification_results WHERE category='document_comparison' AND comparison_readiness='UNRESOLVED') THEN 'BLOCKED' WHEN id IN (SELECT email_id FROM classification_results WHERE category='document_comparison') THEN 'CLASSIFIED' WHEN id IN (SELECT email_id FROM classification_results) THEN 'COMPLETED' ELSE 'NEW' END""")
    op.alter_column("email_messages", "processing_status", nullable=False)
    op.create_check_constraint("ck_email_processing_status", "email_messages", f"processing_status IN ({_STATUSES})")
    op.create_table("processing_events", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False), sa.Column("old_status", sa.String(50)), sa.Column("new_status", sa.String(50), nullable=False), sa.Column("reason_code", sa.String(80), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_processing_events_email_id", "processing_events", ["email_id"])
    op.create_index("ix_processing_events_created_at", "processing_events", ["created_at"])

def downgrade():
    op.drop_table("processing_events")
    op.drop_constraint("ck_email_processing_status", "email_messages", type_="check")
    op.drop_column("email_messages", "processing_status")
