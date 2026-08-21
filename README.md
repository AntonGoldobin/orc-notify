# orc-notify

Multi-tenant notification SaaS. Users register, create agents (API keys), and receive a live feed of events in the browser via SSE. The orchestrator (MVP agent) sends HMAC-signed POSTs to `/v1/events` when threads complete.

## Stack

- **Backend:** FastAPI 0.115 + SQLAlchemy 2.0 async + asyncpg + Alembic
- **Auth:** passlib[argon2] + pyjwt (HS256) + HttpOnly Secure cookies
- **Realtime:** sse-starlette
- **Frontend:** Jinja2 + HTMX (no Node build pipeline)
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

| Method | Path | Auth | Назначение |
|--------|------|------|----------|
| POST   | `/auth/register` | — | email + password |
| POST   | `/auth/login` | — | sets cookie |
| POST   | `/auth/logout` | cookie | clears cookie |
| GET    | `/auth/me` | cookie | current user |
| POST   | `/auth/reset-password` | — | prints reset URL to stdout |
| POST   | `/auth/reset-password/confirm` | — | token + new password |
| GET    | `/api/keys` | cookie | list agents |
| POST   | `/api/keys` | cookie | create agent (secret shown once) |
| DELETE | `/api/keys/{agent_id}` | cookie | revoke |
| POST   | `/api/keys/{agent_id}/rotate-secret` | cookie | new secret |
| GET    | `/v1/agents/{agent_id}/health` | — | last_event_at |
| **POST** | **`/v1/events`** | **HMAC** | **agent webhook** |
| GET    | `/api/rules` | cookie | list rules |
| POST   | `/api/rules` | cookie | create rule |
| PUT    | `/api/rules/{id}` | cookie | update |
| DELETE | `/api/rules/{id}` | cookie | remove |
| GET    | `/api/events/sse` | cookie | live SSE stream |
| GET    | `/api/events?since=` | cookie | history |
| GET    | `/healthz` | — | `{"ok": true}` |

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
