# orc-notify

Multi-tenant notification SaaS. Users register, create agents (API keys), and receive a live feed of events in the browser via SSE. The orchestrator (MVP agent) sends HMAC-signed POSTs to `/v1/events` when threads complete.

## Stack

- **Backend:** FastAPI 0.115 + SQLAlchemy 2.0 async + asyncpg + Alembic
- **Auth:** passlib[argon2] + pyjwt (HS256) + HttpOnly Secure cookies
- **Realtime:** sse-starlette
- **Frontend:** shadcn/ui SPA (React + Vite, served separately as `orc-notify-web`)
- **DB:** Postgres 15 + `citext` extension

## Quick start (local dev)

```bash
# 1. Postgres
docker run -d --name orc-notify-pg -p 5432:5432 \
  -e POSTGRES_USER=notifier -e POSTGRES_PASSWORD=notifier \
  -e POSTGRES_DB=orc-notify postgres:15

# 2. App
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then edit

# 3. Migrate + run
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Deploy (CapRover)

Appended to `services.yaml` in the orchestrator repo. Run from the orchestrator repo:

```bash
orchestrator caprover deploy --project orc-notify
```

Brings up two Captain apps: `orc-notify` (FastAPI) + `orc-notify-postgres` (one-click Postgres-15). App-linking injects `DATABASE_URL` into `orc-notify`.

Live at: `https://orc-notify.orc.golden-antelope.ru`

## API surface

### Topics (Phase 1 — ntfy.sh-compatible pub/sub)

| Method | Path | Auth | Назначение |
|--------|------|------|----------|
| GET    | `/api/topics` | cookie | list user's topics |
| POST   | `/api/topics` | cookie | create topic |
| GET    | `/api/topics/{name}` | cookie | fetch topic |
| PATCH  | `/api/topics/{name}` | cookie | update topic |
| DELETE | `/api/topics/{name}` | cookie | cascade-delete (keys + messages) |
| GET    | `/api/topics/{name}/keys` | cookie | list topic keys (no secret) |
| POST   | `/api/topics/{name}/keys` | cookie | create key (secret shown ONCE) |
| PATCH  | `/api/topics/{name}/keys/{id}` | cookie | rename / rotate secret |
| DELETE | `/api/topics/{name}/keys/{id}` | cookie | revoke |
| POST   | `/{topic}` | cookie or Bearer+HMAC | publish message (ntfy-style) |
| GET    | `/{topic}/json?since=` | cookie or Bearer | poll messages |
| GET    | `/{topic}/sse` | cookie or Bearer | live SSE stream |
| GET    | `/{topic}/raw?since=` | cookie or Bearer | line-delimited JSON |
| GET    | `/{topic}/auth` | cookie or Bearer | capability probe (200 if can read) |

### Legacy (deprecated, will be removed in Phase 5)

| Method | Path | Auth | Назначение |
|--------|------|------|----------|
| GET    | `/api/keys` | cookie | list agents *(deprecated)* |
| POST   | `/api/keys` | cookie | create agent *(deprecated)* |
| DELETE | `/api/keys/{agent_id}` | cookie | revoke *(deprecated)* |
| POST   | `/api/keys/{agent_id}/rotate-secret` | cookie | new secret *(deprecated)* |
| GET    | `/v1/agents/{agent_id}/health` | — | last_event_at *(deprecated)* |
| POST   | `/v1/events` | HMAC | agent webhook *(deprecated)* |
| GET    | `/api/rules` | cookie | list rules *(deprecated)* |
| POST   | `/api/rules` | cookie | create rule *(deprecated)* |
| PUT    | `/api/rules/{id}` | cookie | update *(deprecated)* |
| DELETE | `/api/rules/{id}` | cookie | remove *(deprecated)* |
| GET    | `/api/events/sse` | cookie | live SSE stream *(deprecated)* |
| GET    | `/api/events?since=` | cookie | history *(deprecated)* |

### Auth + meta

| Method | Path | Auth | Назначение |
|--------|------|------|----------|
| POST   | `/auth/register` | — | email + password |
| POST   | `/auth/login` | — | sets cookie |
| POST   | `/auth/logout` | cookie | clears cookie |
| GET    | `/auth/me` | cookie | current user |
| POST   | `/auth/reset-password` | — | prints reset URL to stdout |
| POST   | `/auth/reset-password/confirm` | — | token + new password |
| GET    | `/healthz` | — | `{"ok": true}` |

## Publish envelope (`POST /<topic>`)

ntfy.sh-compatible. Body is raw bytes; metadata in HTTP headers.

```
POST /alerts HTTP/1.1
Authorization: Bearer <key_id>.<hmac_hex>
X-Notifier-Signature: <hmac_hex>
X-Notifier-Timestamp: <unix_seconds>
Title: Deploy failed
Priority: 4
Tags: rotating_light,deploy,ci
Click: https://github.com/.../actions/runs/12345
Icon: https://example.com/icon.png
Actions: [{"action":"view","label":"Open","url":"https://..."}]
Id: deploy-2026-09-08-001
Content-Type: text/plain

<message body>
```

- `Authorization: Bearer <key_id>.<sig>` — `<key_id>` from `POST /api/topics/{name}/keys`, `<sig>` = `HMAC-SHA256(secret, "{ts}:{body}")` hex.
- `X-Notifier-Signature` and `X-Notifier-Timestamp` mirror the bearer sig; both must be present.
- Timestamp window: ±5 min (replay protection).
- `Id:` header provides idempotency — re-publishing the same `Id` returns 200 with the original message (not 201).

Response:

```json
{
  "id": "f6b0d6fe5713487caf31a60496a924e9",
  "time": 1788842025,
  "event": "message",
  "topic": "alerts",
  "title": "Deploy failed",
  "message": "...",
  "priority": 4,
  "tags": ["rotating_light", "deploy", "ci"],
  "click": "https://...",
  "icon": null,
  "actions": null,
  "content_type": "text/plain"
}
```

### Subscribe (`GET /<topic>/{json,sse,raw,auth}`)

All read endpoints require either a cookie session OR a topic key with `read`
scope. Read scopes are NOT HMAC-signed (read is cheaper; HMAC only protects
the write path).

- `/<topic>/json?since=<epoch>` — returns up to 200 messages (NDJSON).
- `/<topic>/sse` — long-lived SSE stream. 15s heartbeat.
- `/<topic>/raw?since=<epoch>` — NDJSON.
- `/<topic>/auth` — 200 with `{can_read: true}` if the caller can read.

## Envelope (agent → /v1/events)

```json
{
  "event": "thread.completed",
  "thread_id": "abc123",
  "project_name": "reelant",
  "user_input": "add dark mode",
  "summary": "...",
  "status": "completed",
  "duration_seconds": 247.3,
  "tasks_count": 5,
  "errors_count": 0,
  "pr_url": null,
  "occurred_at": "2026-08-21T10:05:30Z"
}
```

Headers:
- `X-Notifier-Agent: <agent_id>`
- `X-Notifier-Signature: hex(hmac_sha256(secret, body))` — body is the raw JSON bytes (not the parsed dict)

## Envelope (server → SSE /api/events/sse)

```
event: notification
data: {"id":123, "event":"thread.completed", "thread_id":"abc123", "project_name":"reelant", "summary":"...+", "delivered_at":"2026-08-21T10:05:30Z"}

```

Heartbeat comment every 15s.

## Test

```bash
pytest tests/ -v
```

## License

MIT
