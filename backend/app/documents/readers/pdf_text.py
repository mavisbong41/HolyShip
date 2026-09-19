from __future__ import annotations

import io
from pathlib import Path

from backend.app.documents.models import DocumentFormat, DocumentPage, UnifiedDocument
from backend.app.documents.readers.base import DocumentReader


class PdfTextReader(DocumentReader):
    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        return Path(filename).suffix.lower() == ".pdf"

    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        import pypdf

        try:
            stream = io.BytesIO(content_bytes)
            reader = pypdf.PdfReader(stream)
            pages: list[DocumentPage] = []
            has_images = False

            for idx, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if getattr(page, "images", None) and len(page.images) > 0:
                    has_images = True
                pages.append(DocumentPage(page_number=idx, text=page_text))

            total_text = "\n\n".join(p.text for p in pages if p.text.strip())
            is_empty_or_scanned = len(total_text.strip()) < 30 and (has_images or len(reader.pages) > 0)

            format_type = DocumentFormat.SCANNED_PDF if is_empty_or_scanned else DocumentFormat.PDF_TEXT
            quality = 1.0 if not is_empty_or_scanned else 0.0

            return UnifiedDocument(
                raw_text=total_text,
                pages=pages,
                tables=[],
                format=format_type,
                reader_used="PdfTextReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=quality,
                extraction_status="EXTRACTED" if not is_empty_or_scanned else "PARTIAL",
                metadata={"total_pages": len(reader.pages), "has_images": has_images, "is_scanned": is_empty_or_scanned},
            )
        except Exception as exc:
            return UnifiedDocument(
                raw_text="",
                pages=[],
                tables=[],
                format=DocumentFormat.PDF_TEXT,
                reader_used="PdfTextReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.0,
                extraction_status="FAILED",
                error_message=str(exc),
                metadata={"error": str(exc)},
            )
