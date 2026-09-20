"""Add Phase-3 canonical field extraction persistence.

Revision ID: 20260920_0007
Revises: 20260920_0006
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260920_0007"
down_revision = "20260920_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_extractions",
        sa.Column("extractor_version", sa.String(length=80), nullable=True),
    )
    op.execute(
        "UPDATE document_extractions SET extractor_version = 'materialization-v1' "
        "WHERE extractor_version IS NULL"
    )
    op.alter_column("document_extractions", "extractor_version", nullable=False)

    op.add_column("extracted_fields", sa.Column("raw_label", sa.Text(), nullable=True))
    op.add_column(
        "extracted_fields",
        sa.Column("raw_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "extracted_fields",
        sa.Column("canonical_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "extracted_fields",
        sa.Column("source_location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "extracted_fields",
        sa.Column("mapping_method", sa.String(length=80), nullable=True),
    )
    op.execute(
        "UPDATE extracted_fields SET "
        "raw_value_json = CASE WHEN raw_value IS NULL THEN NULL ELSE to_jsonb(raw_value) END, "
        "source_location = '{}'::jsonb, "
        "status = CASE "
        "WHEN status = 'EXTRACTED' THEN 'RESOLVED' "
        "WHEN status = 'MISSING' THEN 'MISSING' "
        "WHEN status = 'AMBIGUOUS' THEN 'AMBIGUOUS' "
        "ELSE 'UNRESOLVED' END"
    )
    op.alter_column("extracted_fields", "source_location", nullable=False)
    op.create_unique_constraint(
        "uq_extracted_field_extraction_name",
        "extracted_fields",
        ["extraction_id", "field_name"],
    )
    op.create_check_constraint(
        "ck_extracted_field_name",
        "extracted_fields",
        "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
    )
    op.create_check_constraint(
        "ck_extracted_field_status",
        "extracted_fields",
        "status IN ('RESOLVED','MISSING','UNRESOLVED','AMBIGUOUS')",
    )
    op.create_check_constraint(
        "ck_extracted_field_confidence",
        "extracted_fields",
        "confidence >= 0.0 AND confidence <= 1.0",
    )
    op.create_check_constraint(
        "ck_extracted_field_mapping_method",
        "extracted_fields",
        "mapping_method IS NULL OR mapping_method IN ('exact_label','alias_dictionary','bilingual_label_normalization','contextual_business_rule','table_structure','llm_resolved')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_extracted_field_mapping_method", "extracted_fields", type_="check")
    op.drop_constraint("ck_extracted_field_confidence", "extracted_fields", type_="check")
    op.drop_constraint("ck_extracted_field_status", "extracted_fields", type_="check")
    op.drop_constraint("ck_extracted_field_name", "extracted_fields", type_="check")
    op.drop_constraint("uq_extracted_field_extraction_name", "extracted_fields", type_="unique")
    op.drop_column("extracted_fields", "mapping_method")
    op.drop_column("extracted_fields", "source_location")
    op.drop_column("extracted_fields", "canonical_value")
    op.drop_column("extracted_fields", "raw_value_json")
    op.drop_column("extracted_fields", "raw_label")
    op.drop_column("document_extractions", "extractor_version")
