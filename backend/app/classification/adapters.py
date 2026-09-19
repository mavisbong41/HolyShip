from __future__ import annotations

"""
Adapter: converts the ingestion EmailMessage → ClassificationInput.

Keeps the classification engine decoupled from the ingestion layer.
"""

from backend.app.classification.models import ClassificationInput
from backend.app.ingestion.models import EmailMessage


def email_message_to_classification_input(message: EmailMessage) -> ClassificationInput:
    return ClassificationInput(
        external_message_id=message.external_message_id,
        subject=message.subject or "",
        body=message.body or "",
        attachment_filenames=[att.filename for att in message.attachments],
        attachment_count=len(message.attachments),
    )
