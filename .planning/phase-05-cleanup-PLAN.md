# Phase 5 — Final cleanup (legacy code removal)

**Status:** draft (2026-09-08)
**Depends on:** Phase 4 (no Jinja2 UI in repo), Phase 2 + 24h parallel-run (sender cutover stable)
**Risk:** Low-Medium — pure deletion + consolidation, but touches DB schema
**Estimated diff:** ~10 files deleted, ~6 files edited, migration `0003_drop_legacy.py`, ~300 LoC net removal

## Goal

Strip every legacy artefact from the rewrite:
- Old `/v1/events` webhook route (orchestrator-only envelope)
- Old `/api/rules`, `/api/keys` REST routes (replaced by topic-centric equivalents)
- Old `events` + `in_app_notifications` tables (replaced by `messages`)
- Old `channel` column on `rules` (dead data)
- Old `fnmatch.translate` "validation" (didn't actually validate)
- Duplicate Pydantic models in routers
- Hardcoded argon2 dummy hash duplicated in two places
- Misleading UI-SPEC document (`2026-08-25-task-01-B-RESULT.md`)
- Old Captain app definitions (if any) for deprecated services

After Phase 5, orc-notify is **purely** a topic-anchored pub/sub service with shadcn SPA, ntfy.sh-compatible URL contract, Bearer-or-cookie auth, and a single source of truth for Pydantic models.

## Context

This is the "delete the second thing" phase. By now, every user of the old API has had ≥ 7 days (Phase 2 24h + Phase 4 7d) to migrate. Anything still hitting the old routes is either a forgotten client or a test. Both are addressable.

**Pre-flight checks (must pass before this phase starts):**
- `logs/access.log` shows zero hits to `/v1/events` in past 7 days.
- `logs/access.log` shows zero hits to `/api/rules` and `/api/keys` in past 7 days.
- No client code in orchestrator repo references the old routes.
- All `agents` rows migrated to `topic_keys` (or the orchestrator instances have re-provisioned via Phase 2).

## Scope

### In

1. **Migration `0003_drop_legacy.py`**:
   - `DROP TABLE in_app_notifications CASCADE;`
   - `DROP TABLE events CASCADE;` (verify no FK from `messages` first)
   - `ALTER TABLE rules DROP COLUMN channel;`
   - `ALTER TABLE agents RENAME TO topic_keys;` (or `DROP TABLE agents + CREATE TABLE topic_keys` if Phase 1 didn't already do this)
   - Verify and reverse-safe `downgrade()`.
2. **Delete `app/routers/v1_events.py`** — orchestrator-only envelope path.
3. **Delete `app/routers/rules.py`** — replaced by topic-centric equivalents.
4. **Delete `app/routers/api_keys.py`** (or strip to a thin shim if any external consumer still hits `/v1/agents/{id}/health`).
5. **Delete `app/services/events.py`** — old fan-out logic. The new `app/services/messages.py` (Phase 1) replaces it.
6. **Consolidate Pydantic models** in `app/schemas.py`:
   - Move `UserOut` from `routers/auth.py:62-72` to `schemas.py`.
   - Move `AgentOut`, `AgentCreatedOut` from `routers/api_keys.py:36-58` to `schemas.py` (if not already done in Phase 1).
   - All routers import from `schemas.py`.
7. **Single argon2 dummy hash helper** in `app/security.py:constant_time_dummy_hash()`. Used by `/auth/login` and `/auth/reset-password`.
8. **Replace `fnmatch.translate` "validation"** in `rules.py:36-48` with a real validator: `re.fullmatch(r'[a-zA-Z0-9_*?[\].-]+', pattern)` — only allow ntfy.sh-compatible glob chars. (If `rules.py` is deleted, this is moot.)
9. **Delete `2026-08-25-task-01-B-RESULT.md`** (UI-SPEC for Next.js implementation that drifted to Vite).
10. **Update README** — drop "Legacy" / "deprecated" sections. Pure current-state reference.
11. **Update `docs/notifier-deploy.md`** — drop secrets rotation for `WEBHOOK_SECRET_KEY` (no longer needed since `topic_keys` use HMAC SHA256 of timestamp+body, no Fernet at-rest).
12. **Delete `app/secrets.py`** (Fernet helpers) if no other consumer.
13. **Drop the `cryptography` dependency** from `pyproject.toml` if `secrets.py` was its only user.
14. **Captain app audit** — verify no orphan Captain apps for deprecated services (e.g., old `notifier` legacy app).
15. **Update MEMORY** — write `orc-notify-phase-05-cleanup-2026-09-XX.md` documenting what was deleted and the "lessons learned" from the rewrite (e.g., "Next.js spec drift", "Pydantic duplicate sources", "single-process pubsub ceiling").
16. **Update Obsidian Kanban** — close the orc-notify rewrite milestone.
17. **Index entry in `MEMORY.md`** (orchestrator) — `[[orc-notify-phase-05-cleanup-2026-09-XX]]`.

### Out

- **Multi-instance fanout via Postgres LISTEN/NOTIFY** — separate task if scaling demands it.
- **Telegram / Slack / email outbound** — separate task if requested.
- **End-to-end encryption of message body** — separate task.

## Tasks (ordered)

1. Run pre-flight access-log check (`grep /v1/events /var/log/orc-notify/access.log` over past 7 days). Confirm zero hits.
2. Run orchestrator repo grep for old endpoints (`grep -r v1/events /Volumes/SSDNSKIY/VSCODE/orchestrator --include='*.py'`). Confirm zero references.
3. Write migration `0003_drop_legacy.py`. Local round-trip test.
4. Delete routers `v1_events.py`, `rules.py`, `api_keys.py`. Remove from `app/main.py` registration.
5. Delete `app/services/events.py`. Verify no imports remain.
6. Move Pydantic models to `app/schemas.py`. Update imports in remaining routers (`auth.py`, `topics.py`, etc.).
7. Consolidate argon2 dummy hash helper in `app/security.py`.
8. Delete `app/secrets.py`, drop `cryptography` from `pyproject.toml`. `pip install -e .` to verify.
9. Delete `2026-08-25-task-01-B-RESULT.md`.
10. Update `README.md` — drop legacy sections.
11. Update `docs/notifier-deploy.md`.
12. Run `pytest tests/ -q` — all green (legacy test files should already be deleted).
13. Run `pnpm test && pnpm build` in `web/` — all green.
14. **Commit locally** (no push — publish-gate).
15. After deploy verification: write memory note.
16. Update orchestrator's `MEMORY.md` index.

## Verification

### Local

```bash
cd /Volumes/SSDNSKIY/VSCODE/orc-notify
pytest tests/ -q                # green
cd web && pnpm test && pnpm build
alembic upgrade head            # applies 0003
alembic downgrade base          # reverses
alembic upgrade head            # applies again
psql -h localhost -U orc_notify -d orc_notify -c '\dt'
# Expect: only users, password_reset_tokens, topics, topic_keys, messages, rules (without channel), alembic_version
psql -h localhost -U orc_notify -d orc_notify -c '\d rules'
# Expect: no channel column
```

### Production (gated — ALWAYS-ASK)

```bash
curl https://orc-notify.orc.golden-antelope.ru/v1/events -X POST -d '{}' -H 'Content-Type: application/json'
# Expect: HTTP/2 404 or 405 (route removed)
curl https://orc-notify.orc.golden-antelope.ru/api/rules
# Expect: HTTP/2 404 (route removed)
curl https://orc-notify.orc.golden-antelope.ru/healthz
# Expect: HTTP/2 200 (unchanged)
curl -X POST https://orc-notify.orc.golden-antelope.ru/<topic> \
  -H "Authorization: Bearer <token>" \
  -d "Test message after Phase 5"
# Expect: HTTP/2 201
```

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Some forgotten client still hits `/v1/events` | High | Pre-flight access log check. 7-day window from Phase 2. If hit, re-deploy old route temporarily and contact client. |
| Migration fails on a row that references `events` from `messages` | Medium | Migration is `DROP TABLE events CASCADE` — CASCADE handles any FKs. Test round-trip on local data first. |
| `secrets.py` has hidden consumer | Low | `git grep secrets` before deletion. Should show only `v1_events.py` (now deleted) and `api_keys.py` (now deleted). |
| `cryptography` used by something else | Low | `pipdeptree --reverse cryptography` should show only `secrets.py`. |
| Captain has orphan apps we forgot | Low | SSH + `docker service ls` audit. |
| Alembic migration locks during long-running prune | Low | `prune.py` uses `DELETE`, not `ALTER`. No conflict. Migration acquires `ACCESS EXCLUSIVE` on dropped tables only. |

## Success criteria

- [ ] Pre-flight access log shows zero hits to `/v1/events`, `/api/rules`, `/api/keys` in past 7 days.
- [ ] Migration `0003_drop_legacy.py` round-trips locally.
- [ ] `pytest tests/ -q` green.
- [ ] `pnpm test && pnpm build` green.
- [ ] `app/routers/{v1_events,rules,api_keys}.py` deleted.
- [ ] `app/services/events.py`, `app/secrets.py` deleted.
- [ ] `app/schemas.py` is single source of truth for Pydantic models.
- [ ] No `cryptography` dependency in `pyproject.toml`.
- [ ] `2026-08-25-task-01-B-RESULT.md` deleted.
- [ ] Production smoke: old routes return 404, new routes work.
- [ ] Memory note written + indexed in MEMORY.md.
- [ ] Obsidian Kanban milestone closed.
- [ ] STATE.md updated.

## Ponytail markers remaining in final state

| Marker | Ceiling | Upgrade path |
|---|---|---|
| Single-process `TopicPubSub` | 1 orchestrator container, ~10k SSE connections | Postgres LISTEN/NOTIFY + n replicas |
| 7-day default `messages` retention | Trivial DB growth | Per-topic `retention_days` config + Postgres partitioning by month |
| In-Python glob matching on rules (if kept) | O(rules) per publish | GIN index on tags + DB-side filter |
| Bearer token = single HMAC secret per topic key | One key per client; rotation requires re-deploy | Multi-key rotation via key-id header |
