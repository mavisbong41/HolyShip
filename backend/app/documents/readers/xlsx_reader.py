from __future__ import annotations

import io
from pathlib import Path

from backend.app.documents.models import DocumentFormat, DocumentPage, DocumentTable, UnifiedDocument
from backend.app.documents.readers.base import DocumentReader


class XlsxReader(DocumentReader):
    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        return Path(filename).suffix.lower() in (".xlsx", ".xlsm", ".xltx")

    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        import openpyxl

        try:
            stream = io.BytesIO(content_bytes)
            wb = openpyxl.load_workbook(stream, data_only=True)
            text_lines: list[str] = []
            tables: list[DocumentTable] = []

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                sheet_rows: list[list[str]] = []
                for row in ws.iter_rows(values_only=True):
                    row_cells = [str(c).strip().replace("\n", " ") for c in row if c is not None and str(c).strip()]
                    if row_cells:
                        sheet_rows.append(row_cells)
                        if len(row_cells) >= 2:
                            text_lines.append(f"{row_cells[0]}: {' '.join(row_cells[1:])}")
                        elif len(row_cells) == 1:
                            text_lines.append(row_cells[0])

                if sheet_rows:
                    tables.append(DocumentTable(rows=sheet_rows, page_number=1, title=sheet_name))

            full_text = "\n".join(text_lines)
            page = DocumentPage(page_number=1, text=full_text)

            return UnifiedDocument(
                raw_text=full_text,
                pages=[page],
                tables=tables,
                format=DocumentFormat.XLSX,
                reader_used="XlsxReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=1.0 if full_text.strip() else 0.0,
                extraction_status="EXTRACTED" if full_text.strip() else "UNREADABLE",
                metadata={"sheets_count": len(wb.sheetnames)},
            )
        except Exception as exc:
            return UnifiedDocument(
                raw_text="",
                pages=[],
                tables=[],
                format=DocumentFormat.XLSX,
                reader_used="XlsxReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.0,
                extraction_status="FAILED",
                error_message=str(exc),
                metadata={"error": str(exc)},
            )
