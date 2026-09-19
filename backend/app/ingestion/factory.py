from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from backend.app.ingestion.models import IncomingEmailPayload
from backend.app.ingestion.sources import EmailSource, IncomingApiSource, OrganizerHttpSource, StaticBundleSource


class EmailSourceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_type: str
    static_bundle_path: Path | None = None
    organizer_http_url: str | None = None
    incoming_payloads: list[IncomingEmailPayload] | None = None


def build_email_source(config: EmailSourceConfig) -> EmailSource:
    if config.source_type == "STATIC_BUNDLE":
        if config.static_bundle_path is None:
            raise ValueError("static_bundle_path is required for STATIC_BUNDLE")
        return StaticBundleSource(config.static_bundle_path)

    if config.source_type == "ORGANIZER_HTTP":
        if config.organizer_http_url is None:
            raise ValueError("organizer_http_url is required for ORGANIZER_HTTP")
        return OrganizerHttpSource(config.organizer_http_url)

    if config.source_type == "INCOMING_API":
        if config.incoming_payloads is None:
            raise ValueError("incoming_payloads is required for INCOMING_API")
        return IncomingApiSource(config.incoming_payloads)

    raise ValueError(f"Unsupported email source type: {config.source_type}")

