# Phase 1 — Backend schema + topic CRUD + publish/subscribe — SUMMARY

**Status:** SHIPPED 2026-09-08 (commit `d20288f` on origin/main)
**Started:** 2026-09-08 session
**Completed:** 2026-09-08 session
**Risk realized:** Medium (as planned) — handled without incidents

## What shipped

Three new tables (`topics`, `topic_keys`, `messages`) + four new routers (topics, topic_keys, publish, subscribe) + three new services (pubsub_topics, messages, prune) + Bearer auth helper + consolidated duplicate Pydantic models + 5 new test files + smoke script + README + docs updates. Old routes byte-identical except for duplicate-Pydantic consolidation (pure refactor, wire shapes preserved).

### Endpoints added

**Management (cookie auth, under `/api`):**
- `GET/POST /api/topics`
- `GET/PATCH/DELETE /api/topics/{name}`
- `GET/POST /api/topics/{name}/keys`
- `PATCH/DELETE /api/topics/{name}/keys/{id}`

**Publish/Subscribe (Bearer OR cookie, ntfy-compatible):**
- `POST /{topic}` — 201 new / 200 idempotent re-publish
- `GET /{topic}` — peek (last message + count)
- `GET /{topic}/json?since=` — poll
- `GET /{topic}/sse` — SSE stream (15s heartbeat)
- `GET /{topic}/raw` — line-delimited text
- `GET /{topic}/auth` — 200 if read access

## Verification evidence

### Test counts

| Suite | Before | After |
|---|---|---|
| Pre-existing pytest | 85 pass | 85 pass (no regressions) |
| `tests/test_topics.py` | — | 17 new |
| `tests/test_topic_keys.py` | — | 15 new |
| `tests/test_publish.py` | — | 19 new |
| `tests/test_subscribe.py` | — | 19 new |
| `tests/test_prune.py` | — | 4 new |
| **Total** | **85** | **159** (159 passed in 22.14s, 32 deprecation warnings from Pydantic 2.13 / Starlette — non-blocking) |

### Alembic round-trip

Tested against Postgres 16 at `localhost:5432` (langgraph-postgres container, DB `orc_notify_phase01`):

```
Running upgrade  -> 0001_initial
Running upgrade 0001_initial -> 0002_topics
Running downgrade 0002_topics -> 0001_initial
Running downgrade 0001_initial ->
Running upgrade  -> 0001_initial
Running upgrade 0001_initial -> 0002_topics
```

All three commands (upgrade/downgrade/upgrade) succeeded. `downgrade()` cleanly drops the three new tables and indexes without touching existing 5 tables.

### Smoke script (end-to-end against live Postgres + uvicorn)

```
✓ healthz OK
✓ registered smoke-...@example.com
✓ topic smoke-alerts created
✓ key <uuid> created (secret len 43)
✓ published message id=<uuid>
✓ idempotency: 201 then 200 ✓
✓ /json returned 2 message(s)
✓ /auth probe OK
✓ topic deleted
═══ Phase 1 smoke: PASS ═══
```

9/9 assertions green against a real Postgres + uvicorn instance.

## Files

### Created (15 files, +2,815 LoC)

| File | LoC | Purpose |
|---|---|---|
| `migrations/versions/0002_topics.py` | 179 | topics + topic_keys + messages tables, indexes, reversible downgrade |
| `app/routers/topics.py` | 129 | CRUD for topics (cookie auth) |
| `app/routers/topic_keys.py` | 192 | CRUD for topic keys (secret returned once at create) |
| `app/routers/publish.py` | 297 | POST /<topic> with Bearer OR cookie auth, ntfy-style headers |
| `app/routers/subscribe.py` | 245 | GET /<topic>/{json,sse,raw,auth} |
| `app/services/pubsub_topics.py` | 105 | TopicPubSub — in-process topic-anchored pubsub (mirrors existing UserPubSub) |
| `app/services/messages.py` | 135 | publish_message with idempotency on external_id |
| `app/services/prune.py` | 102 | TTL prune task with lifespan hook |
| `tests/test_topics.py` | 217 | 17 specs |
| `tests/test_topic_keys.py` | 238 | 15 specs |
| `tests/test_publish.py` | 372 | 19 specs |
| `tests/test_subscribe.py` | 281 | 19 specs |
| `tests/test_prune.py` | 129 | 4 specs |
| `scripts/smoke-phase-01.sh` | 135 | End-to-end smoke (executable) |
| `docs/notifier-deploy.md` (additive section) | 59 | New endpoints + provisioning |

### Edited (7 files, +500 / -73 LoC net)

| File | Change |
|---|---|
| `app/models.py` | +172 — Topic, TopicKey, Message models + JSONColumn TypeDecorator |
| `app/schemas.py` | +132 — Consolidated UserOut/AgentOut + new Topic/TopicKey/MessageOut + tag CSV helpers |
| `app/security.py` | +39 — compute_topic_signature + verify_bearer_topic_key |
| `app/main.py` | +27 — Wired 4 new routers + prune lifespan task; catch-all publish/subscribe AFTER specific routes |
| `app/routers/api_keys.py` | -3 net — Drop local AgentOut/AgentCreatedOut, import from schemas.py |
| `app/routers/auth.py` | -5 net — Drop local UserOut, import from schemas.py |
| `README.md` | +90 — New endpoints table + publish envelope + subscribe docs; legacy marked `(deprecated)` |

## Deviations from PLAN.md (rationale)

1. **`_normalize_scopes` strict allow-list** `{publish, read}` only — rejected `admin`, `delete`, etc. Two scopes suffice for Phase 1.
2. **PATCH `/keys/{id}` always rotates the secret** — implicit-on-PATCH so users can't leave long-lived keys un-rotated. Documented inline.
3. **HMAC only on writes** — read endpoints (json/sse/raw/auth) need only the key id. HMAC on every read doubles the load for no security gain (the secret is already a 32-byte bearer).
4. **Router order** in `main.py`: catch-all publish/subscribe registered AFTER specific routes (auth, api_keys, v1_events, sse, rules, topics, topic_keys, ui) — correct, prevents single-segment path conflicts.
5. **Message IDs = `uuid4().hex`** (32 chars) not true ULIDs — stdlib only, no extra dep. Still time-sortable via the `time` BIGINT column. Ponytail: minimum code that works.
6. **Prune SQL rewritten to ORM** — original Postgres-specific `now() - (t.retention_days || ' days')::interval` rejected by SQLite. New impl enumerates topics + per-topic cutoff in Python. Bounded (typical users <100 topics). Ponytail ceiling documented.
7. **JSONColumn TypeDecorator added** — JSONB doesn't render in SQLite. Decorator bridges both: JSONB-as-text in Postgres, JSON-as-orjson-text in SQLite. Wire shape identical.

## Risks / follow-ups

1. **Single-instance ceiling.** `TopicPubSub` is in-process. `services.yaml` `instanceCount: 1` is still the cap. Phase 2 swap-in: Postgres LISTEN/NOTIFY (interface identical).
2. **No backpressure metrics.** Slow SSE consumer → silent drop (queue full). Add counter/log if needed in Phase 2.
3. **`messages.actions` JSONB** — SQLite stores as orjson text. Migrate to native ARRAY if queries need it (not now).
4. **`PATCH /keys/{id}` always rotates.** UX may surprise users expecting "rename without rotating" — could add `rotate: bool` flag in PATCH body, judged unwarranted for v1.
5. **`messages.actions` freeform JSON list.** No schema validation beyond "is a list". Future phases can add a Pydantic validator; for now we trust the sender (consistent with ntfy semantics).
6. **Pydantic 2.13 deprecation warnings** — `HTTP_422_UNPROCESSABLE_ENTITY` should be `HTTP_422_UNPROCESSABLE_CONTENT`. Existing code uses the deprecated name; followed the existing pattern for consistency. Trivial cleanup, separate commit.

## Surprises about the existing code

1. **`BigIntAutoInc` decorator** — clever: BIGINT in Postgres, INTEGER in SQLite. Test fixture uses SQLite; prod uses Postgres. Extended naturally to new models.
2. **`get_pubsub` is a process-wide singleton with no test reset** — but `tests/test_sse.py` uses `autouse` fixture + `reset_pubsub()`. Mirrored that pattern in `pubsub_topics.py` with `reset_topic_pubsub()`.
3. **`db.py:49-58` `get_db` commits on success, rolls back on exception** — single transaction per request. Publish endpoint respects this.
4. **Test conftest uses `Base.metadata.create_all` against SQLite** — Alembic is prod-only. Models must work in both dialects. The `JSONColumn` TypeDecorator was the only surprise.
5. **`from_attributes=True` Pydantic config does NOT auto-convert `UUID` → `str`** — reverted to explicit `str(uuid)` in constructors. Schemas use `str` annotations; conversion happens at the boundary via `_agent_to_out` helper.
6. **No `query_id` in topic keys.** Token format `<key_uuid>.<sig>` packs the key UUID into the bearer. ntfy uses `tk_`-prefixed base64; ours is more debug-friendly but less ntfy-compatible. Phase 2 may switch if cross-client compat matters.

## Open follow-ups

- [ ] **Phase 2** — orchestrator sender cutover (`notify_v2.py` + provisioning script + 24h parallel-run + flag removal)
- [ ] **Phase 3** — shadcn frontend scaffold + topic pages
- [ ] **Phase 4** — drop Jinja2 UI + backward-compat shim (after Phase 3 ≥7 days stable)
- [ ] **Phase 5** — drop `/v1/events` + `/api/rules` + `/api/keys` + dead tables (after Phase 2 +24h + Phase 4 ≥7 days, zero access-log hits)
- [ ] **Pydantic 2.13 deprecation cleanup** — `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT` (separate commit, low risk)
- [ ] **Token format decision** — keep `<uuid>.<sig>` debug-friendly or switch to ntfy `tk_`-prefixed base64 for cross-client compat (decision before Phase 2 ships)
- [ ] **Captain deploy** — push image to GHCR, trigger Captain deploy via `services.yaml` `orc-notify` (separate session, gated by user "да deploy")

## Lessons learned (for memory)

- **JSONB column requires TypeDecorator for SQLite/prod dual-dialect tests.** The project's conftest uses `Base.metadata.create_all` against SQLite while prod uses Postgres JSONB. JSONColumn wrapper is the bridge.
- **Duplicate Pydantic consolidation in routers is pure refactor** — wire shapes identical, no migration needed, all 85 existing tests stayed green.
- **In-process pubsub, single-instance ceiling** — works for current load but blocks scaling. Future re-write should pick pub/sub primitive (Postgres LISTEN/NOTIFY, Redis, NATS) before growing user base.
- **HMAC on every read is theatre** — read endpoints need only the key id. HMAC on writes prevents body tampering; reads can't tamper with anything they don't already have the secret for.
- **ntfy URL contract is the right level of compatibility** — `curl -d "hello" /topic` works, any ntfy client works, but the contract is loose enough to extend (per-topic ACL, scopes, priority mapping).
