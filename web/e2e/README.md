# E2E tests (Playwright)

These specs exercise the full stack: **Vite SPA → Vite proxy → FastAPI backend → Postgres**.

## Prerequisites

1. **Backend running.** Either:
   - Local: `cd .. && source .venv/bin/activate && uvicorn app.main:app --port 8000`
   - Remote: `E2E_API_BASE=https://orc-notify.orc.golden-antelope.ru pnpm e2e`

2. **Postgres reachable** by the backend. The orc-notify backend expects Postgres on the
   URL in `orc-notify/.env`. For local, `docker compose up postgres` from the project
   root.

3. **Playwright browsers installed.** First run only:
   ```
   pnpm exec playwright install chromium
   ```

## Run

```bash
# Default — assumes backend on http://localhost:8000
pnpm e2e

# Against remote backend
E2E_API_BASE=https://orc-notify.orc.golden-antelope.ru pnpm e2e

# UI mode for debugging
pnpm e2e:ui
```

## Specs

- `auth.spec.ts` — register → logout → login round-trip; protected-route redirect for anon.
- `happy-path.spec.ts` — full flow: register → create agent → fire HMAC-signed webhook →
  see notification appear on dashboard via live SSE.

The happy-path spec signs the webhook body with HMAC-SHA256(secret, raw_body_bytes) to
match the backend's `app/security.py::sign_event`. See `e2e/utils.ts`.
