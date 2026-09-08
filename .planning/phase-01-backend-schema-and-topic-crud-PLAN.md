# Phase 1 — Backend schema + topic CRUD + publish/subscribe

**Status:** draft (2026-09-08)
**Depends on:** none (first execution phase)
**Risk:** Medium — touches migrations, must not break existing 5 tables
**Estimated diff:** ~12 files, ~700 LoC

## Goal

Add topic-anchored pub/sub to orc-notify **alongside** the existing per-user notification fanout. After this phase, orc-notify has three new tables (`topics`, `topic_keys`, `messages`) and ntfy.sh-compatible URL endpoints (`POST /<topic>`, `GET /<topic>/{json,sse,raw}`), but **no existing behaviour changes** — old `/v1/events`, `/api/rules`, `/api/keys`, `/api/events/sse` keep working untouched.

## Context

See `/Volumes/SSDNSKIY/VSCODE/orc-notify/.planning/redesign-ntfy-style.md` for the full proposal. This phase is the foundation: it puts the new schema in place and proves the URL contract end-to-end before we wire the orchestrator sender (Phase 2) or rewrite the UI (Phase 3).

**Topic scope:** per-user (URL `<topic>` resolves to `<current_user>/<topic>` via auth context).
**Auth default:** private-by-default — every read requires cookie JWT OR a topic key with `read` scope.
**Ponytail marker:** in-process pubsub, single-instance ceiling. Documented in code comment.

## Scope

### In

1. **Alembic migration `0002_topics.py`** — adds three tables + indexes. Idempotent on rollback.
2. **New SQLAlchemy models** in `app/models.py` — `Topic`, `TopicKey`, `Message`.
3. **New Pydantic schemas** in `app/schemas.py` — `TopicIn`, `TopicOut`, `TopicKeyOut`, `TopicKeyCreatedOut`, `MessageIn`, `MessageOut`, `PublishHeaders`. Single source of truth: drop the duplicate `UserOut`/`AgentOut` in `routers/auth.py:62-72` and `routers/api_keys.py:36-58` (cleanup of dead weight, low risk).
4. **New service module `app/services/pubsub_topics.py`** — `TopicPubSub` keyed by `(topic_id, subscriber_id)`, interface compatible with the existing `UserPubSub` (`subscribe`, `publish`, `unsubscribe`, `close`). Process-wide singleton, same shape as existing.
5. **New service module `app/services/messages.py`** — `publish_message(topic, headers, body)` orchestrates: validate → idempotency check (insert with `ON CONFLICT (id) DO NOTHING`) → INSERT → fan-out via `TopicPubSub`. Bearer or cookie auth accepted.
6. **New routers:**
   - `app/routers/topics.py` — `GET/POST /api/topics`, `GET/PATCH/DELETE /api/topics/{name}` (cookie auth).
   - `app/routers/topic_keys.py` — `GET/POST /api/topics/{name}/keys`, `PATCH/DELETE /api/topics/{name}/keys/{id}` (cookie auth; secret returned **once** at create).
   - `app/routers/publish.py` — `POST /<topic>` (Bearer OR cookie; reads `Title`, `Priority`, `Tags`, `Click`, `Icon`, `Actions`, `Id` headers; body = text or JSON). Returns 201 with message object; 200 if `Id` collision (idempotent re-publish).
   - `app/routers/subscribe.py` — `GET /<topic>/json` (?since=), `GET /<topic>/sse` (SSE stream), `GET /<topic>/raw` (line-delimited text), `GET /<topic>/auth` (200 if read access).
7. **Bearer auth helper** in `app/security.py` — `verify_bearer_topic_key(token: str, topic_id: UUID) -> TopicKey`. HMAC-SHA256 over `<timestamp>:<body>`, header `X-Notifier-Signature`, compared constant-time. Mirrors ntfy.sh algorithm verbatim.
8. **TTL pruning** — `app/services/prune.py` runs every 1h as an `asyncio` task started in `main.py:create_app()` lifespan: `DELETE FROM messages WHERE created_at < now() - interval '7 days'`. Configurable per-topic via `Topic.retention_days` (default 7).
9. **Wire new routers** into `app/main.py:create_app()`.
10. **Tests** — `tests/test_topics.py` (CRUD + auth), `tests/test_topic_keys.py` (create/rotate/delete + secret-once), `tests/test_publish.py` (Bearer + cookie auth, idempotency, headers parsing), `tests/test_subscribe.py` (json poll, SSE stream, raw text), `tests/test_prune.py` (TTL).
11. **Smoke script** — `scripts/smoke-phase-01.sh` — register, login, create topic, create key, publish via Bearer, subscribe via SSE, assert message received.

### Out

- **Sender cutover** (orchestrator's `notify.py` change) — Phase 2.
- **Frontend changes** — Phase 3.
- **Removing legacy `/api/rules`, `/api/keys`, `/v1/events`** — Phase 5.
- **Jinja2 UI removal** — Phase 4.
- **Multi-instance fanout** (Postgres LISTEN/NOTIFY) — out of scope. Single-instance ceiling documented.
- **Telegram / Slack / email outbound** — out of scope. The `actions[]` array is the future hook.

## Tasks (ordered)

1. Write `migrations/versions/0002_topics.py` with three tables + FK + indexes + `downgrade()`. Local `alembic upgrade head` + `downgrade base` + `upgrade head` cycle to verify reversibility.
2. Add SQLAlchemy models `Topic`, `TopicKey`, `Message` to `app/models.py`.
3. Add Pydantic schemas to `app/schemas.py`. Remove duplicates in `routers/auth.py` and `routers/api_keys.py`, import from `schemas.py`.
4. Write `app/services/pubsub_topics.py` — `TopicPubSub` class. Mirror `UserPubSub` API: `subscribe(topic_id, subscriber_id) -> asyncio.Queue`, `publish(topic_id, message)`, `unsubscribe(...)`, `close()`. Heartbeat every 15s (matches existing SSE pattern).
5. Write `app/services/messages.py` — `publish_message(...)` + idempotency. SQLite-style fixture in `tests/` should not be needed — pytest uses ephemeral Postgres.
6. Write `app/security.py:verify_bearer_topic_key(...)` — constant-time HMAC compare.
7. Write routers (`topics.py`, `topic_keys.py`, `publish.py`, `subscribe.py`). Each: typed inputs, dependency injection of `get_db`, structured error responses.
8. Write `app/services/prune.py` with `start_prune_task(app)` lifespan hook.
9. Wire routers + prune task into `app/main.py`.
10. Write tests (parallel with router impl). `pytest tests/test_topics.py tests/test_publish.py tests/test_subscribe.py tests/test_prune.py -q` must pass.
11. Write `scripts/smoke-phase-01.sh` — curls `http://localhost:8000/...` with a running backend, prints PASS/FAIL.
12. Update `docs/notifier-deploy.md` with new endpoints (additive section, don't rewrite).
13. Update README API reference — add new endpoints, mark old ones `(deprecated, will be removed in Phase 5)`.
14. **Commit locally only** (no push — `publish-gate.sh` blocks deploy until user approves). Update STATE.md with phase status.

## Verification

### Local

```bash
cd /Volumes/SSDNSKIY/VSCODE/orc-notify
docker compose up postgres -d         # if local dev compose exists; otherwise use existing
alembic upgrade head                  # apply 0002
pytest tests/ -q                      # must include new test files; existing 85 tests stay green
bash scripts/smoke-phase-01.sh        # end-to-end
```

### Production (gated — ALWAYS-ASK)

```bash
# SSH + manual alembic only if Captain image hasn't auto-migrated on container start
# (it does — Dockerfile CMD is `alembic upgrade head && uvicorn`)
# Verify by curl after deploy:
curl https://orc-notify.orc.golden-antelope.ru/healthz  # unchanged
curl https://orc-notify.orc.golden-antelope.ru/api/topics -b cookies.txt  # new, 200 with empty list
```

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Alembic migration corrupts existing data | High | Migration is purely additive (new tables only). No ALTER on existing tables. `downgrade()` drops only the new tables. |
| Concurrent access during migration | Medium | Postgres advisory lock on `topics`/`messages` during `0002` (Alembic default). Brief table-lock window acceptable. |
| Existing 85 tests break | Medium | No changes to `app/routers/{auth,api_keys,v1_events,sse,rules}.py` or `app/services/{events,pubsub}.py`. They stay byte-identical. |
| Bearer token leakage in logs | Medium | `TopicKey.secret_hash` is stored, never plaintext. Secret returned once at create. `verify_bearer_topic_key` constant-time. |
| TTL prune accidentally deletes recent messages | Low | Default 7 days, query uses `created_at < now() - interval '7 days'` not `< 7 days ago`. Easy to extend per-topic later. |
| Topic name collision across users | None | `UNIQUE(user_id, name)` constraint enforced at DB. |

## Success criteria

- [ ] `alembic upgrade head && alembic downgrade base && alembic upgrade head` round-trip succeeds without errors.
- [ ] All pre-existing 85 tests still pass.
- [ ] New tests pass: `pytest tests/test_topics.py tests/test_topic_keys.py tests/test_publish.py tests/test_subscribe.py tests/test_prune.py -q` shows ≥ 30 specs, 100% green.
- [ ] `bash scripts/smoke-phase-01.sh` exits 0 (publish + subscribe round-trip works locally).
- [ ] README updated with new endpoints.
- [ ] Commit local; push deferred (publish-gate).
- [ ] STATE.md updated with phase 1 status = "SHIPPED (pending deploy)".
