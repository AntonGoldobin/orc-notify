# Phase 5 — Final cleanup (legacy code removal) — SUMMARY

**Status:** pending (created 2026-09-08, draft)

## What shipped

_Pending Phase 5 execution._

## Verification evidence

_Pending._

### Test counts

| Suite | Before | After |
|---|---|---|
| Existing vitest | ≥ 50 | ≥ 50 (no change) |
| Existing Playwright | ≥ 4 | ≥ 4 (no change) |
| Existing pytest | ≥ 115 | ≥ 115 (no change) |
| **Total** | **≥ 169** | **≥ 169** |

### DB schema before/after

| Table | Before Phase 5 | After Phase 5 |
|---|---|---|
| `users` | ✓ | ✓ |
| `password_reset_tokens` | ✓ | ✓ |
| `agents` | ✓ | _dropped_ |
| `events` | ✓ | _dropped_ |
| `rules` (with `channel`) | ✓ | ✓ (without `channel`) |
| `in_app_notifications` | ✓ | _dropped_ |
| `topics` (Phase 1) | ✓ | ✓ |
| `topic_keys` (Phase 1) | ✓ | ✓ |
| `messages` (Phase 1) | ✓ | ✓ |

## Files removed

_Pending._

| Path | Reason |
|---|---|
| `app/routers/v1_events.py` | Orchestrator-only envelope, replaced by `/<topic>` |
| `app/routers/rules.py` | Replaced by topic-centric equivalents (if not already in Phase 1) |
| `app/routers/api_keys.py` | Replaced by topic keys (if not already in Phase 1) |
| `app/services/events.py` | Replaced by `app/services/messages.py` |
| `app/secrets.py` | Fernet at-rest encryption no longer needed |
| `2026-08-25-task-01-B-RESULT.md` | Misleading Next.js spec |

## Files edited

_Pending._

| Path | Change |
|---|---|
| `migrations/versions/0003_drop_legacy.py` | NEW — drops legacy tables + channel column |
| `app/main.py` | Remove router registrations |
| `app/schemas.py` | Consolidate Pydantic models (single source of truth) |
| `app/security.py` | Single argon2 dummy hash helper |
| `app/routers/auth.py` | Use consolidated `UserOut` from schemas.py |
| `pyproject.toml` | Drop `cryptography` dep |
| `README.md` | Drop legacy sections |
| `docs/notifier-deploy.md` | Drop legacy rotation procedures |

## Open follow-ups

- [ ] Multi-instance fanout (Postgres LISTEN/NOTIFY) — separate task
- [ ] Telegram / Slack / email outbound — separate task
- [ ] E2E encryption of message body — separate task

## Lessons learned (for memory)

_Document after Phase 5 ships._

- **Spec drift is real.** `2026-08-25-task-01-B-RESULT.md` referenced Next.js; implementation was Vite. Future scaffolds should write the spec only after confirming the framework choice.
- **Duplicate Pydantic models were a maintenance smell.** Three sources of truth for `UserOut`/`AgentOut` made router refactors risky. Single-source consolidation should be a Phase 0 step in any rewrite.
- **In-memory pubsub = single-instance ceiling.** Worked for current load, but blocks scaling. Future re-write should pick a pub/sub primitive (Postgres LISTEN/NOTIFY, Redis, NATS) before growing user base.
- **"Validation" via `fnmatch.translate` was theatre.** Real validation needs explicit character allowlist. Don't trust permissive library functions as validators.
- **Orchestrator-coupled envelopes block generic use.** The `event`/`thread_id`/`status` requirement made orc-notify useless for any non-orchestrator publisher. Adopt standards (ntfy.sh wire format) instead of inventing envelopes.
