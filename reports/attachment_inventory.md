# Phase 2 Attachment Inventory

Generated only from the public participant bundle. No private reference or ground-truth data was read.

- Emails inspected: 520
- Attachments inspected: 250 / 250
- Defined outcome coverage: 100%
- Unhandled exceptions: 0

## Aggregate

### Formats

- `DOCX`: 8
- `PDF_TEXT`: 22
- `PLAIN_TEXT`: 192
- `SCANNED_PDF`: 6
- `XLSX`: 22

### Outcomes

- `BL_FOUND`: 114
- `CORRUPTED_ATTACHMENT`: 2
- `SI_FOUND`: 123
- `UNREADABLE_ATTACHMENT`: 6
- `WRONG_DOCUMENT_TYPE`: 5

### Category and readiness audit

- Category `document_comparison`: 203
- Category `general_message`: 66
- Category `invoice_query`: 84
- Category `new_si_request`: 141
- Category `spam`: 26
- Readiness `AWAITING_DOCUMENTS`: 91
- Readiness `N/A`: 317
- Readiness `READY_FOR_COMPARISON`: 112

### Phase 2 email outcomes

- `AWAITING_DOCUMENTS` / `AWAITING_DOCUMENTS`: 91
- `BLOCKED` / `CORRUPTED_ATTACHMENT`: 2
- `BLOCKED` / `MISSING_REQUIRED_ATTACHMENT`: 5
- `BLOCKED` / `UNREADABLE_ATTACHMENT`: 3
- `BLOCKED` / `WRONG_DOCUMENT_TYPE`: 4
- `EXTRACTING` / `DOCUMENTS_MATERIALIZED`: 98
- `NOT_ENTERED` / `NON_COMPARISON`: 317

## Required special-case lists

- PDF (28): `email_059_SI.pdf`, `email_059_BL.pdf`, `email_160_SI.pdf`, `email_160_BL.pdf`, `email_208_SI.pdf`, `email_208_BL.pdf`, `email_273_SI.pdf`, `email_273_BL.pdf`, `email_313_SI.pdf`, `email_313_BL.pdf`, `email_351_SI.pdf`, `email_351_BL.pdf`, `email_407_SI.pdf`, `email_407_BL.pdf`, `email_411_SI.pdf`, `email_411_BL.pdf`, `email_434_SI.pdf`, `email_434_BL.pdf`, `email_499_SI.pdf`, `email_499_BL.pdf`, `email_511_BL.pdf`, `email_512_SI.pdf`, `email_512_BL.pdf`, `email_513_SI.pdf`, `email_513_BL.pdf`, `email_514_SI.pdf`, `email_514_BL.pdf`, `email_515_BL.pdf`
- DOCX (8): `email_055_BL.docx`, `email_097_BL.docx`, `email_107_BL.docx`, `email_291_BL.docx`, `email_302_BL.docx`, `email_354_BL.docx`, `email_435_BL.docx`, `email_462_BL.docx`
- XLSX (22): `email_005_SI.xlsx`, `email_005_BL.xlsx`, `email_055_SI.xlsx`, `email_097_SI.xlsx`, `email_107_SI.xlsx`, `email_171_SI.xlsx`, `email_171_BL.xlsx`, `email_243_SI.xlsx`, `email_243_BL.xlsx`, `email_291_SI.xlsx`, `email_300_SI.xlsx`, `email_300_BL.xlsx`, `email_302_SI.xlsx`, `email_354_SI.xlsx`, `email_398_SI.xlsx`, `email_398_BL.xlsx`, `email_435_SI.xlsx`, `email_462_SI.xlsx`, `email_481_SI.xlsx`, `email_481_BL.xlsx`, `email_496_SI.xlsx`, `email_496_BL.xlsx`
- Scanned/image-only (6): `email_512_SI.pdf`, `email_512_BL.pdf`, `email_513_SI.pdf`, `email_513_BL.pdf`, `email_514_SI.pdf`, `email_514_BL.pdf`
- Corrupt/truncated (2): `email_511_BL.pdf`, `email_515_BL.pdf`
- Empty/zero-byte (0): None.
- Unsupported (0): None.
- Ambiguous role (0): None.

## WRONG_DOCUMENT_TYPE decisions

- `email_501` / `email_501_BL.txt`: Conflicting business-document marker(s): COMMERCIAL INVOICE; markers=COMMERCIAL INVOICE
- `email_502` / `email_502_BL.txt`: Conflicting business-document marker(s): PACKING LIST; markers=PACKING LIST
- `email_503` / `email_503_BL.txt`: Conflicting business-document marker(s): CERTIFICATE OF ORIGIN; markers=CERTIFICATE OF ORIGIN
- `email_504` / `email_504_BL.txt`: Conflicting business-document marker(s): PACKING LIST; markers=PACKING LIST
- `email_505` / `email_505_BL.txt`: Conflicting business-document marker(s): CERTIFICATE OF ORIGIN; markers=CERTIFICATE OF ORIGIN

## Per-attachment evidence

| Email | Filename | Format | Reader | Readable | Text chars | Table cells | Role | Validation | Outcome | Parse ms | Evidence/anomaly |
|---|---|---|---|---:|---:|---:|---|---|---|---:|---|
| email_001 | email_001_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 702 | 0 | SI | VALID | SI_FOUND | 0.041 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_001 | email_001_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 632 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.038 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_004 | email_004_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 644 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_004 | email_004_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 622 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_005 | email_005_SI.xlsx | XLSX | XlsxReader | yes | 651 | 27 | SI | VALID | SI_FOUND | 259.423 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_005 | email_005_BL.xlsx | XLSX | XlsxReader | yes | 642 | 27 | DRAFT_BL | VALID | BL_FOUND | 3.872 | Content declares draft Bill of Lading role; markers=BILL OF LADING: |
| email_009 | email_009_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 656 | 0 | SI | VALID | SI_FOUND | 0.044 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_009 | email_009_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 663 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_013 | email_013_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 652 | 0 | SI | VALID | SI_FOUND | 0.029 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_013 | email_013_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 636 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_025 | email_025_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 655 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_025 | email_025_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 649 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_031 | email_031_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 678 | 0 | SI | VALID | SI_FOUND | 0.029 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_031 | email_031_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 674 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_032 | email_032_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 670 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_032 | email_032_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 684 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_034 | email_034_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 639 | 0 | SI | VALID | SI_FOUND | 0.035 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_034 | email_034_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 622 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_040 | email_040_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 663 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_040 | email_040_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 625 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_043 | email_043_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 654 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_043 | email_043_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 624 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_044 | email_044_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 678 | 0 | SI | VALID | SI_FOUND | 0.023 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_044 | email_044_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 603 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_046 | email_046_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 755 | 0 | SI | VALID | SI_FOUND | 0.028 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_046 | email_046_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 718 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.028 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_051 | email_051_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 678 | 0 | SI | VALID | SI_FOUND | 0.055 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_051 | email_051_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 641 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.042 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_052 | email_052_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 709 | 0 | SI | VALID | SI_FOUND | 0.034 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_052 | email_052_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 702 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.036 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_055 | email_055_SI.xlsx | XLSX | XlsxReader | yes | 639 | 27 | SI | VALID | SI_FOUND | 4.461 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_055 | email_055_BL.docx | DOCX | DocxReader | yes | 635 | 18 | DRAFT_BL | VALID | BL_FOUND | 111.278 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_056 | email_056_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 652 | 0 | SI | VALID | SI_FOUND | 0.034 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_056 | email_056_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 688 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_058 | email_058_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 611 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_058 | email_058_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 615 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.029 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_059 | email_059_SI.pdf | PDF_TEXT | PdfTextReader | yes | 996 | 0 | SI | VALID | SI_FOUND | 155.900 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_059 | email_059_BL.pdf | PDF_TEXT | PdfTextReader | yes | 1029 | 0 | DRAFT_BL | VALID | BL_FOUND | 9.363 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_064 | email_064_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 667 | 0 | SI | VALID | SI_FOUND | 0.033 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_064 | email_064_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 576 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_065 | email_065_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 734 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_065 | email_065_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 684 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.028 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_068 | email_068_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 671 | 0 | SI | VALID | SI_FOUND | 0.033 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_068 | email_068_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 679 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.058 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_071 | email_071_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 674 | 0 | SI | VALID | SI_FOUND | 0.026 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_071 | email_071_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 672 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.028 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_082 | email_082_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 732 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_082 | email_082_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 720 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.023 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_090 | email_090_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 634 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_090 | email_090_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 599 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.023 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_091 | email_091_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 624 | 0 | SI | VALID | SI_FOUND | 0.034 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_091 | email_091_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 630 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.038 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_096 | email_096_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 736 | 0 | SI | VALID | SI_FOUND | 0.038 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_096 | email_096_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 664 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.036 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_097 | email_097_SI.xlsx | XLSX | XlsxReader | yes | 704 | 27 | SI | VALID | SI_FOUND | 3.950 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_097 | email_097_BL.docx | DOCX | DocxReader | yes | 686 | 18 | DRAFT_BL | VALID | BL_FOUND | 14.643 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_107 | email_107_SI.xlsx | XLSX | XlsxReader | yes | 730 | 27 | SI | VALID | SI_FOUND | 3.888 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_107 | email_107_BL.docx | DOCX | DocxReader | yes | 700 | 18 | DRAFT_BL | VALID | BL_FOUND | 13.935 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_111 | email_111_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 681 | 0 | SI | VALID | SI_FOUND | 0.043 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_111 | email_111_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 670 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.040 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_113 | email_113_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 617 | 0 | SI | VALID | SI_FOUND | 0.034 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_113 | email_113_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 636 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.030 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_118 | email_118_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 668 | 0 | SI | VALID | SI_FOUND | 0.031 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_118 | email_118_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 673 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_119 | email_119_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 664 | 0 | SI | VALID | SI_FOUND | 0.026 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_119 | email_119_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 644 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_121 | email_121_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 637 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_121 | email_121_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 617 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.028 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_128 | email_128_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 674 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_128 | email_128_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 669 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.023 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_129 | email_129_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 666 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_129 | email_129_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 632 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.022 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_132 | email_132_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 656 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_132 | email_132_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 677 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.042 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_133 | email_133_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 704 | 0 | SI | VALID | SI_FOUND | 0.029 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_133 | email_133_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 687 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.029 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_143 | email_143_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 619 | 0 | SI | VALID | SI_FOUND | 0.031 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_143 | email_143_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 597 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_144 | email_144_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 700 | 0 | SI | VALID | SI_FOUND | 0.026 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_144 | email_144_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 684 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_145 | email_145_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 704 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_145 | email_145_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 711 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_146 | email_146_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 611 | 0 | SI | VALID | SI_FOUND | 0.034 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_146 | email_146_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 624 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_160 | email_160_SI.pdf | PDF_TEXT | PdfTextReader | yes | 745 | 0 | SI | VALID | SI_FOUND | 15.700 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_160 | email_160_BL.pdf | PDF_TEXT | PdfTextReader | yes | 731 | 0 | DRAFT_BL | VALID | BL_FOUND | 8.387 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_167 | email_167_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 673 | 0 | SI | VALID | SI_FOUND | 0.032 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_167 | email_167_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 640 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.032 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_171 | email_171_SI.xlsx | XLSX | XlsxReader | yes | 705 | 27 | SI | VALID | SI_FOUND | 3.932 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_171 | email_171_BL.xlsx | XLSX | XlsxReader | yes | 699 | 27 | DRAFT_BL | VALID | BL_FOUND | 3.653 | Content declares draft Bill of Lading role; markers=BILL OF LADING: |
| email_174 | email_174_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 683 | 0 | SI | VALID | SI_FOUND | 0.030 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_174 | email_174_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 719 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.055 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_175 | email_175_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 725 | 0 | SI | VALID | SI_FOUND | 0.031 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_175 | email_175_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 668 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_178 | email_178_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 719 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_178 | email_178_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 642 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_182 | email_182_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 635 | 0 | SI | VALID | SI_FOUND | 0.031 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_182 | email_182_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 625 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_197 | email_197_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 664 | 0 | SI | VALID | SI_FOUND | 0.026 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_197 | email_197_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 701 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.032 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_198 | email_198_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 656 | 0 | SI | VALID | SI_FOUND | 0.039 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_198 | email_198_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 576 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.038 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_208 | email_208_SI.pdf | PDF_TEXT | PdfTextReader | yes | 957 | 0 | SI | VALID | SI_FOUND | 10.422 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_208 | email_208_BL.pdf | PDF_TEXT | PdfTextReader | yes | 962 | 0 | DRAFT_BL | VALID | BL_FOUND | 9.310 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_225 | email_225_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 610 | 0 | SI | VALID | SI_FOUND | 0.030 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_225 | email_225_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 621 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.080 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_227 | email_227_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 698 | 0 | SI | VALID | SI_FOUND | 0.046 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_227 | email_227_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 743 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.051 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_235 | email_235_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 632 | 0 | SI | VALID | SI_FOUND | 0.048 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_235 | email_235_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 642 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.036 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_239 | email_239_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 703 | 0 | SI | VALID | SI_FOUND | 0.050 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_239 | email_239_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 678 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.052 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_243 | email_243_SI.xlsx | XLSX | XlsxReader | yes | 718 | 27 | SI | VALID | SI_FOUND | 6.643 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_243 | email_243_BL.xlsx | XLSX | XlsxReader | yes | 666 | 27 | DRAFT_BL | VALID | BL_FOUND | 6.512 | Content declares draft Bill of Lading role; markers=BILL OF LADING: |
| email_249 | email_249_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 714 | 0 | SI | VALID | SI_FOUND | 0.047 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_249 | email_249_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 678 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.045 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_256 | email_256_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 674 | 0 | SI | VALID | SI_FOUND | 0.056 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_256 | email_256_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 655 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.043 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_270 | email_270_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 653 | 0 | SI | VALID | SI_FOUND | 0.037 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_270 | email_270_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 661 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.044 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_273 | email_273_SI.pdf | PDF_TEXT | PdfTextReader | yes | 791 | 0 | SI | VALID | SI_FOUND | 13.679 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_273 | email_273_BL.pdf | PDF_TEXT | PdfTextReader | yes | 832 | 0 | DRAFT_BL | VALID | BL_FOUND | 10.506 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_275 | email_275_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 707 | 0 | SI | VALID | SI_FOUND | 0.045 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_275 | email_275_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 695 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.036 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_291 | email_291_SI.xlsx | XLSX | XlsxReader | yes | 668 | 27 | SI | VALID | SI_FOUND | 3.960 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_291 | email_291_BL.docx | DOCX | DocxReader | yes | 685 | 18 | DRAFT_BL | VALID | BL_FOUND | 14.271 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_296 | email_296_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 621 | 0 | SI | VALID | SI_FOUND | 0.038 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_296 | email_296_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 685 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_300 | email_300_SI.xlsx | XLSX | XlsxReader | yes | 649 | 27 | SI | VALID | SI_FOUND | 4.111 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_300 | email_300_BL.xlsx | XLSX | XlsxReader | yes | 706 | 27 | DRAFT_BL | VALID | BL_FOUND | 8.651 | Content declares draft Bill of Lading role; markers=BILL OF LADING: |
| email_302 | email_302_SI.xlsx | XLSX | XlsxReader | yes | 699 | 27 | SI | VALID | SI_FOUND | 4.146 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_302 | email_302_BL.docx | DOCX | DocxReader | yes | 746 | 18 | DRAFT_BL | VALID | BL_FOUND | 13.759 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_307 | email_307_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 664 | 0 | SI | VALID | SI_FOUND | 0.034 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_307 | email_307_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 635 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_312 | email_312_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 706 | 0 | SI | VALID | SI_FOUND | 0.030 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_312 | email_312_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 670 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.030 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_313 | email_313_SI.pdf | PDF_TEXT | PdfTextReader | yes | 872 | 0 | SI | VALID | SI_FOUND | 10.011 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_313 | email_313_BL.pdf | PDF_TEXT | PdfTextReader | yes | 859 | 0 | DRAFT_BL | VALID | BL_FOUND | 10.962 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_324 | email_324_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 589 | 0 | SI | VALID | SI_FOUND | 0.032 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_324 | email_324_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 648 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.037 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_334 | email_334_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 623 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_334 | email_334_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 624 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.037 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_335 | email_335_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 674 | 0 | SI | VALID | SI_FOUND | 0.038 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_335 | email_335_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 629 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_342 | email_342_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 589 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_342 | email_342_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 596 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_348 | email_348_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 688 | 0 | SI | VALID | SI_FOUND | 0.030 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_348 | email_348_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 725 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.028 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_349 | email_349_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 725 | 0 | SI | VALID | SI_FOUND | 0.031 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_349 | email_349_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 692 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_351 | email_351_SI.pdf | PDF_TEXT | PdfTextReader | yes | 1381 | 0 | SI | VALID | SI_FOUND | 17.377 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_351 | email_351_BL.pdf | PDF_TEXT | PdfTextReader | yes | 1414 | 0 | DRAFT_BL | VALID | BL_FOUND | 14.209 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_354 | email_354_SI.xlsx | XLSX | XlsxReader | yes | 695 | 27 | SI | VALID | SI_FOUND | 4.079 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_354 | email_354_BL.docx | DOCX | DocxReader | yes | 694 | 18 | DRAFT_BL | VALID | BL_FOUND | 13.144 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_361 | email_361_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 770 | 0 | SI | VALID | SI_FOUND | 0.036 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_361 | email_361_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 769 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.029 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_364 | email_364_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 618 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_364 | email_364_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 633 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_367 | email_367_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 604 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_367 | email_367_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 585 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_377 | email_377_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 660 | 0 | SI | VALID | SI_FOUND | 0.050 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_377 | email_377_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 693 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_378 | email_378_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 699 | 0 | SI | VALID | SI_FOUND | 0.052 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_378 | email_378_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 707 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_379 | email_379_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 675 | 0 | SI | VALID | SI_FOUND | 0.028 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_379 | email_379_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 597 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_383 | email_383_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 655 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_383 | email_383_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 624 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.055 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_391 | email_391_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 659 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_391 | email_391_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 654 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.026 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_398 | email_398_SI.xlsx | XLSX | XlsxReader | yes | 659 | 27 | SI | VALID | SI_FOUND | 3.887 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_398 | email_398_BL.xlsx | XLSX | XlsxReader | yes | 654 | 27 | DRAFT_BL | VALID | BL_FOUND | 3.898 | Content declares draft Bill of Lading role; markers=BILL OF LADING: |
| email_405 | email_405_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 620 | 0 | SI | VALID | SI_FOUND | 0.038 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_405 | email_405_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 634 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_407 | email_407_SI.pdf | PDF_TEXT | PdfTextReader | yes | 1429 | 0 | SI | VALID | SI_FOUND | 18.193 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_407 | email_407_BL.pdf | PDF_TEXT | PdfTextReader | yes | 1391 | 0 | DRAFT_BL | VALID | BL_FOUND | 12.686 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_408 | email_408_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 767 | 0 | SI | VALID | SI_FOUND | 0.031 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_408 | email_408_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 693 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.028 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_409 | email_409_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 614 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_409 | email_409_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 699 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.071 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_410 | email_410_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 645 | 0 | SI | VALID | SI_FOUND | 0.045 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_410 | email_410_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 720 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.048 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_411 | email_411_SI.pdf | PDF_TEXT | PdfTextReader | yes | 957 | 0 | SI | VALID | SI_FOUND | 9.500 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_411 | email_411_BL.pdf | PDF_TEXT | PdfTextReader | yes | 937 | 0 | DRAFT_BL | VALID | BL_FOUND | 9.842 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_416 | email_416_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 642 | 0 | SI | VALID | SI_FOUND | 0.045 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_416 | email_416_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 640 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.029 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_426 | email_426_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 616 | 0 | SI | VALID | SI_FOUND | 0.027 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_426 | email_426_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 627 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_428 | email_428_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 711 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_428 | email_428_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 670 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.025 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_434 | email_434_SI.pdf | PDF_TEXT | PdfTextReader | yes | 1309 | 0 | SI | VALID | SI_FOUND | 11.862 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_434 | email_434_BL.pdf | PDF_TEXT | PdfTextReader | yes | 1333 | 0 | DRAFT_BL | VALID | BL_FOUND | 11.683 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_435 | email_435_SI.xlsx | XLSX | XlsxReader | yes | 696 | 27 | SI | VALID | SI_FOUND | 4.406 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_435 | email_435_BL.docx | DOCX | DocxReader | yes | 686 | 18 | DRAFT_BL | VALID | BL_FOUND | 13.581 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_453 | email_453_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 659 | 0 | SI | VALID | SI_FOUND | 0.043 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_453 | email_453_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 667 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.027 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_462 | email_462_SI.xlsx | XLSX | XlsxReader | yes | 647 | 27 | SI | VALID | SI_FOUND | 4.010 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_462 | email_462_BL.docx | DOCX | DocxReader | yes | 705 | 18 | DRAFT_BL | VALID | BL_FOUND | 13.518 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_468 | email_468_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 595 | 0 | SI | VALID | SI_FOUND | 0.033 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_468 | email_468_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 584 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.030 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_474 | email_474_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 607 | 0 | SI | VALID | SI_FOUND | 0.026 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_474 | email_474_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 665 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.034 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_479 | email_479_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 636 | 0 | SI | VALID | SI_FOUND | 0.048 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_479 | email_479_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 634 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.050 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_481 | email_481_SI.xlsx | XLSX | XlsxReader | yes | 690 | 27 | SI | VALID | SI_FOUND | 11.126 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_481 | email_481_BL.xlsx | XLSX | XlsxReader | yes | 703 | 27 | DRAFT_BL | VALID | BL_FOUND | 4.095 | Content declares draft Bill of Lading role; markers=BILL OF LADING: |
| email_483 | email_483_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 707 | 0 | SI | VALID | SI_FOUND | 0.037 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_483 | email_483_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 718 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.029 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_491 | email_491_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 681 | 0 | SI | VALID | SI_FOUND | 0.029 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_491 | email_491_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 689 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_494 | email_494_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 669 | 0 | SI | VALID | SI_FOUND | 0.035 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_494 | email_494_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 593 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.024 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_496 | email_496_SI.xlsx | XLSX | XlsxReader | yes | 735 | 27 | SI | VALID | SI_FOUND | 4.139 | Content declares SI role: BL INSTRUCTION:; markers=BL INSTRUCTION: |
| email_496 | email_496_BL.xlsx | XLSX | XlsxReader | yes | 823 | 27 | DRAFT_BL | VALID | BL_FOUND | 4.376 | Content declares draft Bill of Lading role; markers=BILL OF LADING: |
| email_498 | email_498_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 605 | 0 | SI | VALID | SI_FOUND | 0.048 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_498 | email_498_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 652 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.040 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_499 | email_499_SI.pdf | PDF_TEXT | PdfTextReader | yes | 745 | 0 | SI | VALID | SI_FOUND | 13.103 | Content declares SI role: BILL OF LADING INSTRUCTION; markers=BILL OF LADING INSTRUCTION |
| email_499 | email_499_BL.pdf | PDF_TEXT | PdfTextReader | yes | 746 | 0 | DRAFT_BL | VALID | BL_FOUND | 7.345 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_501 | email_501_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 719 | 0 | SI | VALID | SI_FOUND | 0.032 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_501 | email_501_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 519 | 0 | OTHER | WRONG_DOCUMENT_TYPE | WRONG_DOCUMENT_TYPE | 0.031 | Conflicting business-document marker(s): COMMERCIAL INVOICE; markers=COMMERCIAL INVOICE |
| email_502 | email_502_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 623 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_502 | email_502_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 384 | 0 | OTHER | WRONG_DOCUMENT_TYPE | WRONG_DOCUMENT_TYPE | 0.023 | Conflicting business-document marker(s): PACKING LIST; markers=PACKING LIST |
| email_503 | email_503_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 699 | 0 | SI | VALID | SI_FOUND | 0.033 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_503 | email_503_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 381 | 0 | OTHER | WRONG_DOCUMENT_TYPE | WRONG_DOCUMENT_TYPE | 0.025 | Conflicting business-document marker(s): CERTIFICATE OF ORIGIN; markers=CERTIFICATE OF ORIGIN |
| email_504 | email_504_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 638 | 0 | SI | VALID | SI_FOUND | 0.032 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_504 | email_504_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 555 | 0 | OTHER | WRONG_DOCUMENT_TYPE | WRONG_DOCUMENT_TYPE | 0.030 | Conflicting business-document marker(s): PACKING LIST; markers=PACKING LIST |
| email_505 | email_505_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 664 | 0 | SI | VALID | SI_FOUND | 0.026 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_505 | email_505_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 364 | 0 | OTHER | WRONG_DOCUMENT_TYPE | WRONG_DOCUMENT_TYPE | 0.027 | Conflicting business-document marker(s): CERTIFICATE OF ORIGIN; markers=CERTIFICATE OF ORIGIN |
| email_507 | email_507_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 692 | 0 | SI | VALID | SI_FOUND | 0.030 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_509 | email_509_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 668 | 0 | SI | VALID | SI_FOUND | 0.024 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_511 | email_511_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 598 | 0 | SI | VALID | SI_FOUND | 0.026 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_511 | email_511_BL.pdf | PDF_TEXT | PdfTextReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | CORRUPTED_ATTACHMENT | 0.332 | Stream has ended unexpectedly |
| email_512 | email_512_SI.pdf | SCANNED_PDF | OcrReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | UNREADABLE_ATTACHMENT | 2.476 | OCR engine (tesseract) is not installed or not found in PATH |
| email_512 | email_512_BL.pdf | SCANNED_PDF | OcrReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | UNREADABLE_ATTACHMENT | 2.025 | OCR engine (tesseract) is not installed or not found in PATH |
| email_513 | email_513_SI.pdf | SCANNED_PDF | OcrReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | UNREADABLE_ATTACHMENT | 1.968 | OCR engine (tesseract) is not installed or not found in PATH |
| email_513 | email_513_BL.pdf | SCANNED_PDF | OcrReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | UNREADABLE_ATTACHMENT | 1.859 | OCR engine (tesseract) is not installed or not found in PATH |
| email_514 | email_514_SI.pdf | SCANNED_PDF | OcrReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | UNREADABLE_ATTACHMENT | 1.688 | OCR engine (tesseract) is not installed or not found in PATH |
| email_514 | email_514_BL.pdf | SCANNED_PDF | OcrReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | UNREADABLE_ATTACHMENT | 1.685 | OCR engine (tesseract) is not installed or not found in PATH |
| email_515 | email_515_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 683 | 0 | SI | VALID | SI_FOUND | 0.028 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_515 | email_515_BL.pdf | PDF_TEXT | PdfTextReader | no | 0 | 0 | UNKNOWN | INCONCLUSIVE | CORRUPTED_ATTACHMENT | 0.294 | Stream has ended unexpectedly |
| email_516 | email_516_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 454 | 0 | SI | VALID | SI_FOUND | 0.030 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_516 | email_516_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 654 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.028 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_517 | email_517_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 466 | 0 | SI | VALID | SI_FOUND | 0.038 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_517 | email_517_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 707 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.035 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_518 | email_518_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 459 | 0 | SI | VALID | SI_FOUND | 0.025 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_518 | email_518_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 658 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.023 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_519 | email_519_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 414 | 0 | SI | VALID | SI_FOUND | 0.036 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_519 | email_519_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 617 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.041 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |
| email_520 | email_520_SI.txt | PLAIN_TEXT | PlainTextReader | yes | 386 | 0 | SI | VALID | SI_FOUND | 0.031 | Content declares SI role: SHIPPING INSTRUCTION; markers=SHIPPING INSTRUCTION |
| email_520 | email_520_BL.txt | PLAIN_TEXT | PlainTextReader | yes | 620 | 0 | DRAFT_BL | VALID | BL_FOUND | 0.037 | Content declares draft Bill of Lading role; markers=BILL OF LADING (DRAFT) |

## Per-email Phase 2 gate audit

This offline corpus audit materializes all public attachments for coverage; the runtime lazy-retrieval invariant is separately proven by the requirement-marked PostgreSQL test.

| Email | Category | Readiness | Attachments | Phase 2 status | Reason code |
|---|---|---|---:|---|---|
| email_001 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_002 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_003 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_004 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_005 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_006 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_007 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_008 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_009 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_010 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_011 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_012 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_013 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_014 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_015 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_016 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_017 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_018 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_019 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_020 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_021 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_022 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_023 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_024 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_025 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_026 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_027 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_028 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_029 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_030 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_031 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_032 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_033 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_034 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_035 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_036 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_037 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_038 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_039 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_040 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_041 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_042 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_043 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_044 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_045 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_046 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_047 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_048 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_049 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_050 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_051 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_052 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_053 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_054 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_055 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_056 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_057 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_058 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_059 | new_si_request | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_060 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_061 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_062 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_063 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_064 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_065 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_066 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_067 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_068 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_069 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_070 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_071 | new_si_request | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_072 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_073 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_074 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_075 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_076 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_077 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_078 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_079 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_080 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_081 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_082 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_083 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_084 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_085 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_086 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_087 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_088 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_089 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_090 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_091 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_092 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_093 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_094 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_095 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_096 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_097 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_098 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_099 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_100 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_101 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_102 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_103 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_104 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_105 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_106 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_107 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_108 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_109 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_110 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_111 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_112 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_113 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_114 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_115 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_116 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_117 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_118 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_119 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_120 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_121 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_122 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_123 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_124 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_125 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_126 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_127 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_128 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_129 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_130 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_131 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_132 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_133 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_134 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_135 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_136 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_137 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_138 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_139 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_140 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_141 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_142 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_143 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_144 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_145 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_146 | new_si_request | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_147 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_148 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_149 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_150 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_151 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_152 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_153 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_154 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_155 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_156 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_157 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_158 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_159 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_160 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_161 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_162 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_163 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_164 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_165 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_166 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_167 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_168 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_169 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_170 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_171 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_172 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_173 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_174 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_175 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_176 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_177 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_178 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_179 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_180 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_181 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_182 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_183 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_184 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_185 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_186 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_187 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_188 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_189 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_190 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_191 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_192 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_193 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_194 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_195 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_196 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_197 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_198 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_199 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_200 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_201 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_202 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_203 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_204 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_205 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_206 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_207 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_208 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_209 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_210 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_211 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_212 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_213 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_214 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_215 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_216 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_217 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_218 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_219 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_220 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_221 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_222 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_223 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_224 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_225 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_226 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_227 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_228 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_229 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_230 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_231 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_232 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_233 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_234 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_235 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_236 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_237 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_238 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_239 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_240 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_241 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_242 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_243 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_244 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_245 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_246 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_247 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_248 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_249 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_250 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_251 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_252 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_253 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_254 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_255 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_256 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_257 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_258 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_259 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_260 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_261 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_262 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_263 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_264 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_265 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_266 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_267 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_268 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_269 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_270 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_271 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_272 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_273 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_274 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_275 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_276 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_277 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_278 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_279 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_280 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_281 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_282 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_283 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_284 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_285 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_286 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_287 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_288 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_289 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_290 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_291 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_292 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_293 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_294 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_295 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_296 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_297 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_298 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_299 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_300 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_301 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_302 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_303 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_304 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_305 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_306 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_307 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_308 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_309 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_310 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_311 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_312 | new_si_request | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_313 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_314 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_315 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_316 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_317 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_318 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_319 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_320 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_321 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_322 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_323 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_324 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_325 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_326 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_327 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_328 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_329 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_330 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_331 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_332 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_333 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_334 | new_si_request | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_335 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_336 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_337 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_338 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_339 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_340 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_341 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_342 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_343 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_344 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_345 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_346 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_347 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_348 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_349 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_350 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_351 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_352 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_353 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_354 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_355 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_356 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_357 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_358 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_359 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_360 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_361 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_362 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_363 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_364 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_365 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_366 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_367 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_368 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_369 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_370 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_371 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_372 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_373 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_374 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_375 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_376 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_377 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_378 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_379 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_380 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_381 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_382 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_383 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_384 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_385 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_386 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_387 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_388 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_389 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_390 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_391 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_392 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_393 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_394 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_395 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_396 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_397 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_398 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_399 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_400 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_401 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_402 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_403 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_404 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_405 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_406 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_407 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_408 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_409 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_410 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_411 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_412 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_413 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_414 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_415 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_416 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_417 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_418 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_419 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_420 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_421 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_422 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_423 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_424 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_425 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_426 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_427 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_428 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_429 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_430 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_431 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_432 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_433 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_434 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_435 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_436 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_437 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_438 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_439 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_440 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_441 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_442 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_443 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_444 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_445 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_446 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_447 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_448 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_449 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_450 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_451 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_452 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_453 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_454 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_455 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_456 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_457 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_458 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_459 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_460 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_461 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_462 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_463 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_464 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_465 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_466 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_467 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_468 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_469 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_470 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_471 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_472 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_473 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_474 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_475 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_476 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_477 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_478 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_479 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_480 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_481 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_482 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_483 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_484 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_485 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_486 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_487 | new_si_request | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_488 | general_message | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_489 | spam | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_490 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_491 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_492 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_493 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_494 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_495 | document_comparison | AWAITING_DOCUMENTS | 0 | AWAITING_DOCUMENTS | AWAITING_DOCUMENTS |
| email_496 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_497 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_498 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_499 | general_message | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_500 | invoice_query | N/A | 0 | NOT_ENTERED | NON_COMPARISON |
| email_501 | invoice_query | N/A | 2 | NOT_ENTERED | NON_COMPARISON |
| email_502 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | WRONG_DOCUMENT_TYPE |
| email_503 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | WRONG_DOCUMENT_TYPE |
| email_504 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | WRONG_DOCUMENT_TYPE |
| email_505 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | WRONG_DOCUMENT_TYPE |
| email_506 | document_comparison | READY_FOR_COMPARISON | 0 | BLOCKED | MISSING_REQUIRED_ATTACHMENT |
| email_507 | document_comparison | READY_FOR_COMPARISON | 1 | BLOCKED | MISSING_REQUIRED_ATTACHMENT |
| email_508 | document_comparison | READY_FOR_COMPARISON | 0 | BLOCKED | MISSING_REQUIRED_ATTACHMENT |
| email_509 | document_comparison | READY_FOR_COMPARISON | 1 | BLOCKED | MISSING_REQUIRED_ATTACHMENT |
| email_510 | document_comparison | READY_FOR_COMPARISON | 0 | BLOCKED | MISSING_REQUIRED_ATTACHMENT |
| email_511 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | CORRUPTED_ATTACHMENT |
| email_512 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | UNREADABLE_ATTACHMENT |
| email_513 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | UNREADABLE_ATTACHMENT |
| email_514 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | UNREADABLE_ATTACHMENT |
| email_515 | document_comparison | READY_FOR_COMPARISON | 2 | BLOCKED | CORRUPTED_ATTACHMENT |
| email_516 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_517 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_518 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_519 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
| email_520 | document_comparison | READY_FOR_COMPARISON | 2 | EXTRACTING | DOCUMENTS_MATERIALIZED |
