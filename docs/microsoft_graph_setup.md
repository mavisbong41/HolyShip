# Microsoft Graph deployment setup

## Application registration

Create a tenant application with application permissions appropriate to the deployment mailbox, including message read/write and mail send, and grant tenant admin consent. Scope mailbox access with Exchange application-access controls where possible.

Configure only the backend:

```text
MICROSOFT_GRAPH_ENABLED=true
MICROSOFT_GRAPH_TENANT_ID=<tenant-id>
MICROSOFT_GRAPH_CLIENT_ID=<application-id>
MICROSOFT_GRAPH_CLIENT_SECRET=<secret>
MICROSOFT_GRAPH_MAILBOX=<mailbox-user-id-or-address>
MICROSOFT_GRAPH_SYNC_ENABLED=true
MICROSOFT_GRAPH_SYNC_INTERVAL_SECONDS=60
MICROSOFT_GRAPH_WEBHOOK_URL=https://<public-host>/api/v1/graph/notifications
MICROSOFT_GRAPH_WEBHOOK_CLIENT_STATE=<random-high-entropy-value>
MICROSOFT_GRAPH_SUBSCRIPTION_LIFETIME_MINUTES=4200
MICROSOFT_GRAPH_SUBSCRIPTION_RENEW_BEFORE_MINUTES=30
```

Never place tenant, client, or webhook secrets in Dashboard or Outlook configuration.

## Runtime model

The worker uses immutable Graph message IDs, stores its mailbox-specific delta cursor in `ingestion_checkpoints`, and submits newly discovered mail to the common HolyShip ingestion pipeline. A successful page commit advances `nextLink`; the final page stores `deltaLink`. Failure retains the last committed cursor and records an error.

The backend creates a subscription when none exists, renews it before expiry, and creates a replacement after expiry. The public HTTPS webhook must allow Graph's validation-token request. Notifications must carry the configured `clientState`; accepted notifications only wake the worker. Delta remains the source of truth, so duplicate or out-of-order notifications are safe.

## Production checks

1. Apply migrations through `20260925_0019`.
2. Start with Graph sync enabled and verify the checkpoint records a subscription ID and expiration.
3. Deliver a new message and verify one HolyShip record is created and processed.
4. Repeat delta, then test read/category/folder, delete, and restore changes against the same record.
5. Restart the backend and verify polling resumes from the persisted cursor.
6. Send only after explicit user confirmation and verify `SENT` follows Graph success; exercise failure/retry with a non-production recipient first.

The repository tests use mocked Graph transport and isolated PostgreSQL. Live tenant verification must be recorded separately for each deployment.
