from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from backend.app.core.config import Settings


class GraphClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class GraphResponse:
    status: int
    payload: dict[str, Any] | None = None


Transport = Callable[[str, str, dict[str, str], bytes | None, float], GraphResponse]


def _urlopen_transport(method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> GraphResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            payload = json.loads(raw) if raw else None
            return GraphResponse(response.status, payload)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise GraphClientError(f"Microsoft Graph HTTP {exc.code}: {raw[:1000]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GraphClientError(f"Microsoft Graph request failed: {exc}") from exc


class MicrosoftGraphClient:
    """Server-side client-credentials Graph boundary; tokens never reach a UI."""

    def __init__(self, settings: Settings, *, transport: Transport | None = None):
        if not settings.microsoft_graph_enabled:
            raise GraphClientError("Microsoft Graph integration is not configured")
        self.settings = settings
        self.transport = transport or _urlopen_transport
        self._access_token: str | None = None

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        secret = self.settings.microsoft_graph_client_secret
        body = urllib.parse.urlencode({
            "client_id": self.settings.microsoft_graph_client_id or "",
            "client_secret": secret.get_secret_value() if secret else "",
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }).encode()
        url = f"https://login.microsoftonline.com/{urllib.parse.quote(self.settings.microsoft_graph_tenant_id or '')}/oauth2/v2.0/token"
        response = self.transport("POST", url, {"Content-Type": "application/x-www-form-urlencoded"}, body, self.settings.microsoft_graph_timeout_seconds)
        token = (response.payload or {}).get("access_token")
        if response.status != 200 or not isinstance(token, str) or not token:
            raise GraphClientError("Microsoft Graph token response was invalid")
        self._access_token = token
        return token

    def request(self, method: str, path_or_url: str, payload: dict[str, Any] | None = None) -> GraphResponse:
        url = path_or_url if path_or_url.startswith("https://") else f"{self.settings.microsoft_graph_base_url.rstrip('/')}/{path_or_url.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/json",
            "Prefer": 'IdType="ImmutableId"',
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        return self.transport(method, url, headers, body, self.settings.microsoft_graph_timeout_seconds)

    def reply(self, message_id: str, message: str) -> None:
        mailbox = urllib.parse.quote(self.settings.microsoft_graph_mailbox or "", safe="")
        encoded_id = urllib.parse.quote(message_id, safe="")
        response = self.request("POST", f"users/{mailbox}/messages/{encoded_id}/reply", {"comment": message})
        if response.status not in {200, 202, 204}:
            raise GraphClientError(f"Microsoft Graph reply returned HTTP {response.status}")

    def delta(self, delta_url: str | None = None) -> tuple[list[dict[str, Any]], str | None, str | None]:
        mailbox = urllib.parse.quote(self.settings.microsoft_graph_mailbox or "", safe="")
        url = delta_url or f"users/{mailbox}/messages/delta?$select=id,internetMessageId,isRead,categories,parentFolderId,subject,receivedDateTime,hasAttachments"
        response = self.request("GET", url)
        if response.status != 200 or not isinstance(response.payload, dict):
            raise GraphClientError("Microsoft Graph delta response was invalid")
        payload = response.payload
        return list(payload.get("value") or []), payload.get("@odata.nextLink"), payload.get("@odata.deltaLink")

    def message(self, message_id: str) -> dict[str, Any]:
        mailbox = urllib.parse.quote(self.settings.microsoft_graph_mailbox or "", safe="")
        encoded_id = urllib.parse.quote(message_id, safe="")
        path = (
            f"users/{mailbox}/messages/{encoded_id}"
            "?$select=id,internetMessageId,subject,body,from,toRecipients,receivedDateTime,isRead,categories,parentFolderId,hasAttachments"
            "&$expand=attachments($select=id,name,contentType,contentBytes)"
        )
        response = self.request("GET", path)
        if response.status != 200 or not isinstance(response.payload, dict):
            raise GraphClientError("Microsoft Graph message response was invalid")
        return response.payload

    def set_categories(self, message_id: str, categories: list[str]) -> None:
        mailbox = urllib.parse.quote(self.settings.microsoft_graph_mailbox or "", safe="")
        encoded_id = urllib.parse.quote(message_id, safe="")
        response = self.request("PATCH", f"users/{mailbox}/messages/{encoded_id}", {"categories": categories})
        if response.status not in {200, 204}:
            raise GraphClientError(f"Microsoft Graph category update returned HTTP {response.status}")

    def create_subscription(self, notification_url: str, client_state: str) -> dict[str, Any]:
        mailbox = urllib.parse.quote(self.settings.microsoft_graph_mailbox or "", safe="")
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.settings.microsoft_graph_subscription_lifetime_minutes)
        response = self.request("POST", "subscriptions", {
            "changeType": "created,updated,deleted",
            "notificationUrl": notification_url,
            "resource": f"/users/{mailbox}/messages",
            "expirationDateTime": expires.isoformat(),
            "clientState": client_state,
        })
        if response.status not in {200, 201} or not isinstance(response.payload, dict) or not response.payload.get("id"):
            raise GraphClientError("Microsoft Graph subscription creation failed")
        return response.payload

    def renew_subscription(self, subscription_id: str) -> dict[str, Any]:
        encoded_id = urllib.parse.quote(subscription_id, safe="")
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.settings.microsoft_graph_subscription_lifetime_minutes)
        response = self.request("PATCH", f"subscriptions/{encoded_id}", {"expirationDateTime": expires.isoformat()})
        if response.status != 200 or not isinstance(response.payload, dict):
            raise GraphClientError("Microsoft Graph subscription renewal failed")
        return response.payload
