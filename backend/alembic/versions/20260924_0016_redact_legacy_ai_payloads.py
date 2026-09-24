"""Redact legacy raw AI request/question payloads.

Revision ID: 20260924_0016
Revises: 20260921_0015
"""

from alembic import op


revision = "20260924_0016"
down_revision = "20260921_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase-6 originally persisted the complete resolver request, including
    # field evidence. Preserve cache identity/result truth, but replace the
    # request payload with non-sensitive audit metadata.
    op.execute(
        """
        UPDATE ai_resolutions
        SET request_json = jsonb_strip_nulls(
            jsonb_build_object(
                'purpose', purpose,
                'field', field_name,
                'escalation_reason', request_json ->> 'escalation_reason',
                'disclosed_fields', jsonb_build_array(field_name),
                'disclosure_categories',
                    CASE
                        WHEN purpose = 'SEMANTIC'
                            THEN jsonb_build_array(
                                'field_name',
                                'si_value',
                                'bl_value',
                                'field_evidence'
                            )
                        ELSE jsonb_build_array(
                            'field_name',
                            'document_role',
                            'field_evidence'
                        )
                    END,
                'legacy_payload_redacted', true
            )
        )
        """
    )

    # Earlier Human Review AI events stored the free-form user question.
    # Remove that raw text while keeping enough metadata to explain that an
    # AI request occurred.
    op.execute(
        """
        UPDATE human_review_events
        SET details = (details - 'question') || jsonb_build_object(
            'question_length', length(COALESCE(details ->> 'question', '')),
            'legacy_question_redacted', true
        )
        WHERE action = 'AI_ASSISTANT_ASKED'
          AND details ? 'question'
        """
    )


def downgrade() -> None:
    # Intentionally irreversible: a downgrade must not recreate sensitive raw
    # AI prompts/evidence once they have been redacted.
    pass
