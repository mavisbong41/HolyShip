"""
Generate standard RFC 5322 / RFC 2045 .eml files from organizer hackathon bundle.

Preserves:
- Original sender ('from')
- Original subject
- Original body
- Original attachments (TXT, PDF, DOCX, XLSX)
- Message-ID (<email_xxx@holyship.internal>)
- Formatted Date headers spaced over recent hours so they appear ordered in Outlook
"""

import html
import json
import mimetypes
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

# Ensure mime types are registered
mimetypes.add_type("application/pdf", ".pdf")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
mimetypes.add_type("text/plain", ".txt")

BUNDLE_PATH = Path(r"c:\Users\Zi Shan\holyship\sdoc-hackathon-bundle")
OUTPUT_DIR = Path(r"c:\Users\Zi Shan\holyship\demo_emails_eml")
RECIPIENT_EMAIL = "captain.jack@holyship.com"

# The 19 curated cases requested by user
SELECTED_CASES = [
    # Star cases for direct inspection
    {"id": "email_408", "label": "MATCH - 7 canonical fields match (Happy Path)"},
    {"id": "email_025", "label": "MISMATCH - POD & Container Count mismatch"},
    {"id": "email_468", "label": "MISMATCH - POL & Container Count mismatch"},
    {"id": "email_364", "label": "MATCH - Text variation resolved via safe normalization"},
    {"id": "email_479", "label": "MATCH - Descriptive / bilingual label mapping"},
    {"id": "email_507", "label": "HUMAN REVIEW - Missing BL in comparison"},
    {"id": "email_509", "label": "HUMAN REVIEW - Missing BL #2"},
    {"id": "email_332", "label": "CLAIMED ATTACHMENT MISSING - Operational email without attachments"},
    {"id": "email_511", "label": "HUMAN REVIEW - Corrupted / unreadable BL"},
    {"id": "email_515", "label": "HUMAN REVIEW - Corrupted / unreadable BL #2"},
    {"id": "email_160", "label": "MULTI-FORMAT - Both SI and BL are PDF"},
    {"id": "email_005", "label": "MULTI-FORMAT - Both SI and BL are XLSX"},
    {"id": "email_055", "label": "MULTI-FORMAT - SI is XLSX, BL is DOCX"},
    {"id": "email_217", "label": "NEW SI REQUEST - Structured SI body in email"},
    {"id": "email_469", "label": "NEW SI REQUEST - Customer SI submission"},
    {"id": "email_155", "label": "INVOICE QUERY - Freight and local charge invoice inquiry"},
    {"id": "email_329", "label": "SPAM / PHISHING - Suspicious customs fee payment link"},
    {"id": "email_254", "label": "SPAM / PHISHING - Fake mailbox quota warning"},
    {"id": "email_417", "label": "SPAM / FINANCIAL - Wire transfer scam"},
]


def generate_emls():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_time = datetime.now(timezone.utc) - timedelta(hours=len(SELECTED_CASES))

    generated_files = []

    for idx, item in enumerate(SELECTED_CASES):
        case_id = item["id"]
        label = item["label"]
        json_path = BUNDLE_PATH / "inbox" / f"{case_id}.json"

        if not json_path.exists():
            print(f"Warning: {json_path} not found, skipping.")
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sender = data.get("from", "shipping@example.com")
        subject = data.get("subject", "Shipping Document")
        body = data.get("body", "")
        attachment_refs = data.get("attachments", [])

        # Construct standard RFC 5322 Email Message
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = RECIPIENT_EMAIL

        # Set realistic progressive date
        msg_date = base_time + timedelta(minutes=idx * 20)
        msg["Date"] = formatdate(msg_date.timestamp(), localtime=False, usegmt=True)

        # External Message ID & custom HolyShip tracking header
        msg["Message-ID"] = f"<{case_id}>"
        msg["X-HolyShip-Case-ID"] = case_id
        msg["X-Demo-Description"] = label

        # Set email plain-text and rich HTML body for Outlook
        msg.set_content(body, charset="utf-8")
        escaped_body = html.escape(body).replace("\n", "<br/>")
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #1e293b;">
<div>{escaped_body}</div>
</body>
</html>"""
        msg.add_alternative(html_content, subtype="html")

        # Attach real documents
        for att_ref in attachment_refs:
            att_path = BUNDLE_PATH / att_ref
            if not att_path.exists():
                print(f"Warning: attachment {att_path} not found for {case_id}")
                continue

            content = att_path.read_bytes()
            filename = att_path.name
            ctype, encoding = mimetypes.guess_type(filename)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)

            msg.add_attachment(
                content,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

        # Save as .eml file
        # Format name with index so it sorts nicely in file explorer: 01_email_408_MATCH.eml
        prefix = f"{idx + 1:02d}_{case_id}"
        out_filename = f"{prefix}.eml"
        out_path = OUTPUT_DIR / out_filename

        with open(out_path, "wb") as f:
            f.write(msg.as_bytes())

        generated_files.append((out_filename, sender, len(attachment_refs), label))

    print(f"\n Successfully generated {len(generated_files)} .eml files in:")
    print(f"  {OUTPUT_DIR}\n")
    print(f"{'#':<3} | {'File Name':<28} | {'From':<32} | {'Atts':<4} | {'Demo Case'}")
    print("-" * 110)
    for i, (fn, snd, atts, lbl) in enumerate(generated_files, 1):
        print(f"{i:<3} | {fn:<28} | {snd:<32} | {atts:<4} | {lbl}")


if __name__ == "__main__":
    generate_emls()
