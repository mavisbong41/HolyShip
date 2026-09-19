import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backend.app.ingestion.sources import OrganizerHttpSource


EMAILS = [
    {
        "email_id": "email_001",
        "from": "docs@example.com",
        "subject": "Please verify draft BL",
        "body": "Please compare the attached shipping instruction and draft BL.",
        "attachments": [
            "attachments/email_001_SI.txt",
            "attachments/email_001_BL.pdf",
        ],
    },
    {
        "email_id": "email_002",
        "from": "billing@example.com",
        "subject": "Invoice question",
        "body": "Can you clarify this payment amount?",
        "attachments": [],
    },
]


class OrganizerApiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/emails":
            self._json(EMAILS)
            return
        if self.path == "/emails/email_001":
            self._json(EMAILS[0])
            return
        if self.path == "/emails/email_002":
            self._json(EMAILS[1])
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return

    def _json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_organizer_http_source_maps_list_response_to_email_messages():
    with http_source() as base_url:
        source = OrganizerHttpSource(base_url)

        messages = list(source.iter_messages())

    assert [message.external_message_id for message in messages] == ["email_001", "email_002"]
    assert all(message.source_type == "ORGANIZER_HTTP" for message in messages)
    assert messages[0].attachments[0].filename == "email_001_SI.txt"
    assert messages[0].attachments[1].content_type == "application/pdf"
    assert len(messages[0].content_hash) == 64


def test_organizer_http_source_fetches_single_message():
    with http_source() as base_url:
        source = OrganizerHttpSource(base_url)

        message = source.get_message("email_002")

    assert message.external_message_id == "email_002"
    assert message.sender == "billing@example.com"
    assert message.attachments == []


class http_source:
    def __enter__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), OrganizerApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

