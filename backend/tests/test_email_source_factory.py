from backend.app.ingestion.factory import EmailSourceConfig, build_email_source
from backend.app.ingestion.models import IncomingEmailPayload
from backend.app.ingestion.sources import IncomingApiSource, OrganizerHttpSource, StaticBundleSource


def test_factory_builds_static_bundle_source():
    source = build_email_source(
        EmailSourceConfig(
            source_type="STATIC_BUNDLE",
            static_bundle_path="sdoc-hackathon-bundle",
        )
    )

    assert isinstance(source, StaticBundleSource)


def test_factory_builds_organizer_http_source():
    source = build_email_source(
        EmailSourceConfig(
            source_type="ORGANIZER_HTTP",
            organizer_http_url="http://localhost:8080",
        )
    )

    assert isinstance(source, OrganizerHttpSource)


def test_factory_builds_incoming_api_source():
    source = build_email_source(
        EmailSourceConfig(
            source_type="INCOMING_API",
            incoming_payloads=[IncomingEmailPayload(subject="Hello")],
        )
    )

    assert isinstance(source, IncomingApiSource)

