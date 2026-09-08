# orc-notify → ntfy-style redesign proposal

**Status:** proposal (not yet planned/executed). Awaiting user direction.
**Author:** orchestrator session 2026-09-08.
**Goal:** evolve orc-notify from "per-user fanout SSE" into a topic-based pub/sub notification service compatible with ntfy.sh conventions, with a shadcn-style SPA.

---

## 1. Where we are today (current pain)

### What's actually in the repo

- `app/` — FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + sse-starlette.
  - 6 tables: `users`, `password_reset_tokens`, `agents`, `events`, `rules`, `in_app_notifications`.
  - Inbound model is HMAC-signed `POST /v1/events` with an envelope tightly coupled to the orchestrator: `event`, `thread_id`, `status` are required (`v1_events.py:69-85`). Generic publish doesn't fit.
  - "Publish" in the code (`services/pubsub.publish`) is per-user fanout to one or more SSE queues (`dict[user_id, set[asyncio.Queue]]`). It's not topic pub/sub.
  - Rules are user-owned, not topic-owned. `SUPPORTED_CHANNELS = {"sse"}` literal; the `channel` column is dead data (`rules.py:33`).
  - Rule matching happens in Python (`fnmatchcase` over ALL enabled rules for the user — `services/events.py:68-71`). No DB-side glob.
  - `fnmatch.translate` "validation" doesn't actually validate — `[unclosed` passes (`rules.py:36-48`).
- `web/` — React 19 + Vite 8 + HeroUI v3.2.4 + Tailwind v4 + React Router 7 + TanStack Query 5.
  - 8 pages: Login, Register, Reset, Dashboard, Keys, Rules, Settings, Root. Dashboard uses `EventSource` for live tail.
  - The previously-specced Next.js implementation drifted — actual code is plain Vite SPA. Spec is now misleading.
- `app/templates/` + `app/routers/ui.py` — **legacy Jinja2 + HTMX UI still mounted and broken** (htmx.min.js missing → register/login silently no-op).

### Concretely broken or held-together-by-tape

1. **Two UIs in one repo.** Jinja2 is dead-weight but still routable. nginx SPA fallback doesn't cover it.
2. **"Publish" is the wrong word.** Code calls it publish but no message ever leaves the server. There's no Telegram/email/outbound-webhook path.
3. **One channel (SSE), not extensible.** `channel` column is a placeholder lie.
4. **Coupled to orchestrator envelope.** Can't accept a plain `curl -d "hello"` publish.
5. **No idempotency.** A retried POST creates a duplicate event row + duplicate notification.
6. **No pruning.** `events` and `in_app_notifications` grow unbounded (flagged in `docs/notifier-deploy.md:106-108`).
7. **In-memory pubsub blocks horizontal scaling.** `services.yaml` says `instanceCount: 1`, that's the cap.
8. **Spec drift.** UI-SPEC references Next.js; implementation is Vite SPA.
9. **SPA not registered in `services.yaml`.** `web/` Dockerfile exists but no Captain app entry under orchestrator management.
10. **Duplicate Pydantic models.** `UserOut`/`AgentOut` declared in `schemas.py`, `routers/auth.py`, `routers/api_keys.py` — three sources of truth.

---

## 2. Where we want to be (target state)

### 2.1 Backend: topic-anchored pub/sub, ntfy.sh-compatible

The fundamental shift: **from per-user notification fanout to topic-anchored message bus**.

#### URL conventions (ntfy-compatible)

```
# Topic-anchored paths — work with curl, ntfy-cli, web subscribers alike
POST   /<topic>                  # publish
GET    /<topic>                  # peek (last message + count)
GET    /<topic>/json             # poll messages (?since=<id>)
GET    /<topic>/sse              # SSE stream
GET    /<topic>/ws               # WebSocket
GET    /<topic>/raw              # line-delimited text
GET    /<topic>/auth             # 200 if user/token can read

# Management (cookie-authenticated, under /api)
GET    /api/topics
POST   /api/topics
GET    /api/topics/{name}
PATCH  /api/topics/{name}
DELETE /api/topics/{name}

GET    /api/topics/{name}/keys          # publish credentials
POST   /api/topics/{name}/keys
PATCH  /api/topics/{name}/keys/{id}     # rotate
DELETE /api/topics/{name}/keys/{id}

GET    /api/topics/{name}/messages      # browse history
```

Why ntfy-compatible URLs: every existing ntfy client (CLI, mobile apps, scripts) works against orc-notify unchanged. Brain compatibility > custom cleverness.

#### Auth model (two layers)

| Caller | Auth | Use case |
|---|---|---|
| Browser SPA | Cookie JWT (existing `notifier_session`) | UI access |
| External clients (curl, scripts) | Bearer `<publish_token>` | Programmatic publish + read |
| Per-topic keys | Scoped to one topic: `publish` / `read` / both | Multi-tenant app keys |

`agents` table → `topic_keys` (rename + simplify):
- `id`, `topic_id`, `name`, `secret_hash` (HMAC key, returned **once** at create), `scopes` (`publish`, `read`), `last_used_at`, `created_at`.
- Drop the orchestrator-specific HMAC envelope — adopt ntfy's `Authorization: Bearer tk_...` semantics.

`rules` table → keep, narrow purpose:
- "Forward messages matching pattern X from topic A to topic B with priority Y."
- Becomes a side-effect/automation layer on top of pub/sub, not the primary routing primitive.

#### Message schema (matches ntfy.sh wire format)

```json
{
  "id": "01H8XGJWBXBAQ4ZEXAMPLE",
  "time": 1757678400,
  "event": "message",
  "topic": "alerts",
  "title": "Deploy failed",
  "message": "R.119 worker image :66 healthcheck timed out",
  "priority": 4,
  "tags": ["deploy", "ci", "rotating_light"],
  "click": "https://github.com/.../actions/runs/12345",
  "icon": null,
  "actions": [
    {"action": "view", "label": "Open run", "url": "..."},
    {"action": "http", "label": "Retry", "url": "...", "method": "POST"}
  ],
  "content_type": "text/plain"
}
```

DB storage: `messages(id text PK, topic_id, external_id, time, event, title, body, priority smallint, tags text[], click text, icon text, actions jsonb, content_type text, created_at)`. Idempotency on `external_id` (client-provided `Id:` header) OR `id` collision.

#### Fan-out: in-process pubsub, ready to swap for Postgres LISTEN/NOTIFY

Keep the `UserPubSub`-style design but key it by `(topic_id, subscriber_id)` instead of `user_id`. Wrap behind an interface so a future swap to Redis pub/sub or Postgres LISTEN/NOTIFY is one module. **Don't prematurely distribute** — single instance is fine for current load.

#### Pruning: TTL-based, single SQL job

```sql
DELETE FROM messages WHERE created_at < now() - interval '7 days';
```

Run as a Postgres cron (`pg_cron` extension) or a small `asyncio` task in the FastAPI app on a 1h schedule. 7-day default, configurable per topic.

#### Migration path for the orchestrator sender

`langgraph-cloud-agents/app/orchestrator/notify.py` currently POSTs the orchestrator envelope. Change to:

```
POST <ORC_NOTIFY_BASE>/orchestrator-events
Authorization: Bearer <ORCHESTRATOR_TOPIC_TOKEN>
Title: ...
Priority: ...
Tags: deploy,ci
Message: ...
```

This is a sender-side change: orchestrator gets one default topic on first run (`orchestrator-events`), publishes plain ntfy messages there. No more orchestrator-shaped envelopes; orc-notify stops pretending to be orchestrator-only.

### 2.2 Frontend: shadcn-style SPA, topic-first

#### Stack delta

| Today (HeroUI v3) | Target (shadcn-style) |
|---|---|
| `@heroui/react` 3.2.4 + `@heroui/styles` (eager all-base-styles, 416 KB CSS) | `shadcn/ui` components copied into `web/src/components/ui/` |
| Tailwind v4 (keep) | Tailwind v4 (keep — same CSS-first) |
| `useOverlayState`, `Card.Header/Title`, `Modal.Body` | `react-aria-components` underneath shadcn primitives |
| No command palette | `cmdk` (Cmd+K) for topic switching |
| No toast library beyond HeroUI primitives | `sonner` |
| No icon library | `lucide-react` (shadcn ships with these) |

shadcn/ui gives us copy-paste control — components live in our repo, can be patched in-place, no surprise minor-version breakage (HeroUI v3 had 8 gotchas during initial scaffold per the memory note).

#### Page map

```
/                       redirect → /topics or /login
/login                  auth (shadcn Card + Form + Button)
/register               auth
/reset?token=…          auth

/topics                 # sidebar nav target. Grid of TopicCard: name, unread badge, last activity, sparkline of recent priorities.
/topics/:name           # tabbed:
  ├── Messages         # virtualized list, SSE live tail, filter by priority/tag, Cmd+K to jump
  ├── Publish          # copy-paste curl example (one-click copy), test form
  └── Settings         # rename, danger-zone delete, default priority, list of topic keys

/topics/:name/keys      # manage topic keys (separate page for deep linking)

/keys                   # global view of all topic keys across topics
/docs                   # auto-generated per-topic copy-paste examples + API reference
/settings               # profile + change password + danger zone
```

Sidebar layout (shadcn `<Sidebar>`):
```
┌──────────────┐
│ 🏠 Topics    │
│ 🔑 Keys      │
│ 📖 Docs      │
│ ⚙ Settings  │
├──────────────┤
│ + New topic │
└──────────────┘
```

Cmd+K (`cmdk`): fuzzy search across topics + global nav.

#### shadcn components used (concrete list)

`button`, `input`, `textarea`, `label`, `select`, `switch`, `checkbox`, `card`, `table`, `badge`, `separator`, `scroll-area`, `sidebar`, `dialog`, `dropdown-menu`, `tabs`, `tooltip`, `sonner` (toast), `command`, `skeleton`, `avatar`, `hover-card`, `form` (react-hook-form + zod).

### 2.3 What stays

- Cookie JWT auth (`/auth/*`, `notifier_session` cookie, argon2id, pyjwt HS256). Tested, deployed, working.
- Postgres + Alembic. Same DB. Migration adds tables, doesn't replace.
- Vite 8 + React 19 + TypeScript. Same SPA shell.
- TanStack Query v5. Same data-fetching layer.
- React Router 7. Same routing.
- nginx reverse-proxy pattern (`web/nginx.conf`). Same Captain app shape.
- `web/Dockerfile` multi-stage build. Same pipeline.

### 2.4 What goes

- `app/templates/*` + `app/routers/ui.py` — delete after SPA cutover.
- `app/static/*` (sse-client.js, app.css) — delete with Jinja2 UI.
- `in_app_notifications` table — folded into direct subscriptions; deliveries are implicit per-SSE-connection.
- `channel` column on `rules` — drop or repurpose.
- Dead `fnmatch.translate` validation — replace with a real glob validator (or just zod `.regex()` on the pattern).
- Duplicate Pydantic models in `routers/auth.py` and `routers/api_keys.py` — keep one source of truth (`app/schemas.py`).
- Hardcoded argon2 dummy hash duplicated in two places — single helper.
- `2026-08-25-task-01-B-RESULT.md` UI-SPEC (Next.js drift) — replace with this document.

---

## 3. Migration plan (phased)

Each phase = one PR + one deploy, atomic. Pause between phases for user review.

### Phase 0 — **this proposal** (no code)

You are here. User picks: proceed, modify, defer.

### Phase 1 — Backend schema + topic CRUD (read-only + manage)

New migration `0002_topics.py`:
- `topics(id uuid PK, user_id FK, name text, display_name text, created_at, UNIQUE(user_id, name))`
- `topic_keys(id uuid PK, topic_id FK, name text, secret_hash text, scopes text[], created_at, last_used_at)`
- `messages(id text PK, topic_id FK, external_id text NULL, time int, event text, title text, body text, priority smallint, tags text[], click text NULL, icon text NULL, actions jsonb, content_type text, created_at)`
- Indexes: `(topic_id, created_at DESC)`, `messages(external_id) WHERE external_id IS NOT NULL`.

New routers:
- `app/routers/topics.py` — full CRUD + key management (cookie auth).
- `app/routers/publish.py` — `POST /<topic>` with Bearer or cookie. HMAC verification for Bearer keys.
- `app/routers/subscribe.py` — `GET /<topic>/json|sse|raw` (cookie auth OR topic read-scope key).

NO changes to `v1_events.py`, `agents`, `rules`, `in_app_notifications` — keep working. Old `/api/keys`, `/api/rules` still return their current shapes.

### Phase 2 — Sender cutover (orchestrator side)

`langgraph-cloud-agents/app/orchestrator/notify.py`: drop the orchestrator envelope, POST plain ntfy messages to `ORC_NOTIFY_BASE/orchestrator-events` with Bearer token. Each orchestrator instance gets a topic-key on first run (provisioning flow: orchestrator registers, gets token back, persists).

### Phase 3 — Frontend: shadcn scaffold + topic pages

`web/`:
- `pnpm dlx shadcn@latest init` — Tailwind v4 config (already in place).
- Add shadcn primitives to `web/src/components/ui/`.
- Delete `web/src/pages/{Keys,Rules}.tsx` (replaced by topic-centric pages).
- Add `web/src/pages/{Topics,TopicDetail}.tsx` + `PublishTab` + `MessagesTab` + `SettingsTab`.
- Old pages still routable but deprecation banner.

### Phase 4 — Frontend cutover

Set root path to `/topics`. Old routes return 410 Gone (or redirect to new equivalents). Remove Jinja2 templates + `app/routers/ui.py`. Remove `app/static/*`.

### Phase 5 — Cleanup

- Delete `events` + `in_app_notifications` tables (after verifying `messages` covers the read paths).
- Drop `channel` column on `rules`.
- Delete `2026-08-25-task-01-B-RESULT.md` (misleading spec).
- Single Pydantic source of truth in `app/schemas.py`.

---

## 4. Open questions for the user

1. **Topic naming scope.** Globally unique topic names (ntfy.sh style — `mytopic` is one name across all users) or per-user scoped (`<user>/<topic>`)? Trade-off: globally unique is simpler but creates name squatting concerns; per-user is what ntfy.sh uses internally for user topics.

2. **Read auth default.** Are topics private-by-default (always require auth to read) or public-by-default with optional auth (ntfy.sh style)? For a SaaS product private-by-default is the safer default.

3. **Idempotency window.** How long to remember `Id:` header values for dedup? ntfy.sh uses 12h. Shorter = less DB growth, longer = safer retries.

4. **Migration policy for orchestrator's existing in-flight webhooks.** Cut over hard (one deploy), or run both in parallel for 24h and migrate senders gradually?

5. **shadcn-style preference over HeroUI.** Anything specific you liked about HeroUI v3 we should preserve in the shadcn port? E.g. the `data-app-theme` decoupling trick is shadcn-amenable but worth keeping verbatim.

6. **First-class Discord/Slack/Telegram delivery.** Out of scope for this proposal but worth flagging — if you want server-side delivery to non-HTTP channels, the message schema's `actions` array is the right hook for it (Phase 5.5, post-cleanup).

---

## 5. Risks & ceilings

| Risk | Severity | Mitigation |
|---|---|---|
| ntfy.sh URL conventions collide with our future routes | Low | Pick `/{topic}` for publish only (POST). Management under `/api/...`. No conflict. |
| shadcn/ui components get out of sync with upstream | Medium | Pin a snapshot at scaffold time; update quarterly, not weekly. |
| Bearer-token HMAC verification drifts from ntfy.sh semantics | Low | Use the SAME algorithm ntfy.sh documents (HMAC-SHA256 of `time` + body, header `X-Notifier-Signature`); document parity in code comment. |
| Sender cutover during in-flight notifications | Medium | Phase 2 keeps `v1_events` working. Old + new endpoints both alive during transition. |
| `messages` table growth before TTL job lands | Low | Add TTL job in Phase 1, not Phase 5. |
| `UserPubSub` rename breaks existing SSE clients | Low | Old `/api/events/sse` route alias remains in Phase 1. Removed in Phase 4. |

**ponytail markers (deliberate simplifications):**
- Single-instance pubsub, ceiling: 1 orchestrator container, ~10k concurrent SSE connections. Upgrade: Postgres LISTEN/NOTIFY + n replicas.
- 7-day message retention, ceiling: trivial DB growth. Upgrade: per-topic retention policy + Postgres partitioning.
- In-Python glob matching on rules, ceiling: O(rules) per publish. Upgrade: GIN index on tags + DB-side filter.

---

## 6. Out of scope (explicit non-goals)

- Server-side delivery to Telegram/Slack/email — Phase 5.5 if requested.
- Multi-region replication — far future.
- End-to-end encryption of message body — ntfy.sh doesn't do this either; flag for later.
- Mobile push (APNs/FCM) — ntfy.sh has UnifiedPush, but it's a heavy lift; defer.
- Forwarding/integration marketplace — single-user forwarding rules only.
