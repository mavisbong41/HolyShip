import json

from pydantic import SecretStr

from backend.app.core.config import Settings
from backend.app.ingestion.graph_client import GraphResponse, MicrosoftGraphClient


def _settings():
    return Settings(
        _env_file=None, microsoft_graph_enabled=True,
        microsoft_graph_tenant_id="tenant", microsoft_graph_client_id="client",
        microsoft_graph_client_secret=SecretStr("secret"), microsoft_graph_mailbox="ops@example.com",
    )


def test_graph_reply_uses_server_token_and_verifies_success():
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body))
        if "oauth2" in url:
            return GraphResponse(200, {"access_token": "server-token"})
        return GraphResponse(202)
    MicrosoftGraphClient(_settings(), transport=transport).reply("message/id", "Confirmed")
    assert calls[1][0] == "POST"
    assert calls[1][2]["Authorization"] == "Bearer server-token"
    assert json.loads(calls[1][3]) == {"comment": "Confirmed"}
    assert "secret" not in calls[1][1]


def test_graph_delta_returns_provider_cursor():
    def transport(method, url, headers, body, timeout):
        if "oauth2" in url:
            return GraphResponse(200, {"access_token": "token"})
        return GraphResponse(200, {"value": [{"id": "one"}], "@odata.deltaLink": "https://graph.microsoft.com/delta-token"})
    rows, next_url, delta_url = MicrosoftGraphClient(_settings(), transport=transport).delta()
    assert rows == [{"id": "one"}]
    assert next_url is None
    assert delta_url.endswith("delta-token")


def test_graph_subscription_create_and_renew_use_server_side_client_state():
    calls = []
    def transport(method, url, headers, body, timeout):
        if "oauth2" in url:
            calls.append((method, url, headers, None))
            return GraphResponse(200, {"access_token": "token"})
        calls.append((method, url, headers, json.loads(body) if body else None))
        if method == "POST":
            return GraphResponse(201, {"id": "sub-1", "expirationDateTime": "2026-09-25T06:00:00Z"})
        return GraphResponse(200, {"id": "sub-1", "expirationDateTime": "2026-09-25T07:00:00Z"})

    client = MicrosoftGraphClient(_settings(), transport=transport)
    created = client.create_subscription("https://example.com/api/v1/graph/notifications", "opaque-state")
    renewed = client.renew_subscription("sub-1")

    assert created["id"] == renewed["id"] == "sub-1"
    assert calls[1][3]["clientState"] == "opaque-state"
    assert calls[1][3]["resource"].endswith("/messages")
    assert calls[2][0] == "PATCH"
    assert "clientState" not in calls[2][3]
    assert calls[1][2]["Prefer"] == 'IdType="ImmutableId"'
