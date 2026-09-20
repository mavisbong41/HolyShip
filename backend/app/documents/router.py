from __future__ import annotations

from pathlib import Path
from typing import Sequence

from backend.app.documents.models import (
    DocumentFormat,
    DocumentRoutingResult,
    DocumentType,
    RoutedAttachment,
    UnifiedDocument,
)
from backend.app.documents.role_validation import DocumentRoleValidator
from backend.app.ingestion.models import AttachmentMetadata


class DocumentRouter:
    """
    Classifies attachments into SI, DRAFT_BL, OTHER, or UNKNOWN.
    Evaluates filename patterns, extensions, and content signals.
    Enforces validation rules (missing SI/BL, multiple candidates, uncertainty).
    """

    def __init__(self, role_validator: DocumentRoleValidator | None = None):
        self.role_validator = role_validator or DocumentRoleValidator()

    def detect_format(self, filename: str) -> DocumentFormat:
        ext = Path(filename).suffix.lower()
        if ext in (".txt", ".text", ".csv", ""):
            return DocumentFormat.PLAIN_TEXT
        if ext == ".pdf":
            return DocumentFormat.PDF_TEXT
        if ext == ".docx":
            return DocumentFormat.DOCX
        if ext in (".xlsx", ".xlsm", ".xltx"):
            return DocumentFormat.XLSX
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            return DocumentFormat.IMAGE
        return DocumentFormat.UNKNOWN

    def classify_attachment(
        self,
        attachment: AttachmentMetadata,
        peek_text: str | None = None,
    ) -> RoutedAttachment:
        doc_format = self.detect_format(attachment.filename)
        validation = self.role_validator.validate(
            UnifiedDocument(
                raw_text=peek_text or "",
                format=doc_format,
                filename=attachment.filename,
                source_reference=attachment.source_reference,
            )
        )
        return RoutedAttachment(
            filename=attachment.filename,
            source_reference=attachment.source_reference,
            document_type=validation.document_type,
            format=doc_format,
            confidence=validation.confidence,
            evidence=validation.evidence,
        )

    def route_attachments(
        self,
        attachments: Sequence[AttachmentMetadata],
        peek_texts: dict[str, str] | None = None,
    ) -> DocumentRoutingResult:
        peek_texts = peek_texts or {}
        routed_list = [
            self.classify_attachment(att, peek_texts.get(att.source_reference or att.filename))
            for att in attachments
        ]

        si_candidates = [r for r in routed_list if r.document_type == DocumentType.SI]
        bl_candidates = [r for r in routed_list if r.document_type == DocumentType.DRAFT_BL]
        other_list = [r for r in routed_list if r.document_type not in (DocumentType.SI, DocumentType.DRAFT_BL)]
        unknown_list = [r for r in routed_list if r.document_type == DocumentType.UNKNOWN]

        # Case 1: Multiple SI candidates
        if len(si_candidates) > 1:
            return DocumentRoutingResult(
                other_attachments=routed_list,
                human_review_required=True,
                human_review_reason_code="MULTIPLE_SI_CANDIDATES",
                human_review_reason_text=f"Found {len(si_candidates)} Shipping Instruction candidates: {[c.filename for c in si_candidates]}",
            )

        # Case 2: Multiple BL candidates
        if len(bl_candidates) > 1:
            return DocumentRoutingResult(
                other_attachments=routed_list,
                human_review_required=True,
                human_review_reason_code="MULTIPLE_BL_CANDIDATES",
                human_review_reason_text=f"Found {len(bl_candidates)} Draft BL candidates: {[c.filename for c in bl_candidates]}",
            )

        # Case 3: Missing both
        if not si_candidates and not bl_candidates:
            reason_code = "DOCUMENT_TYPE_UNCERTAIN" if unknown_list else "MISSING_SI"
            return DocumentRoutingResult(
                other_attachments=routed_list,
                human_review_required=True,
                human_review_reason_code=reason_code,
                human_review_reason_text="Neither Shipping Instruction nor Draft BL could be identified in email attachments.",
            )

        # Case 4: Missing SI
        if not si_candidates:
            return DocumentRoutingResult(
                bl_attachment=bl_candidates[0],
                other_attachments=other_list,
                human_review_required=True,
                human_review_reason_code="MISSING_SI",
                human_review_reason_text="Draft BL found, but Shipping Instruction (SI) is missing from attachments.",
            )

        # Case 5: Missing BL
        if not bl_candidates:
            return DocumentRoutingResult(
                si_attachment=si_candidates[0],
                other_attachments=other_list,
                human_review_required=True,
                human_review_reason_code="MISSING_BL",
                human_review_reason_text="Shipping Instruction found, but Draft Bill of Lading (BL) is missing from attachments.",
            )

        # Success: exactly 1 SI and 1 BL
        return DocumentRoutingResult(
            si_attachment=si_candidates[0],
            bl_attachment=bl_candidates[0],
            other_attachments=other_list,
            human_review_required=False,
        )
