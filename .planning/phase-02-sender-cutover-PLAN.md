# Phase 2 — Orchestrator sender cutover

**Status:** draft (2026-09-08)
**Depends on:** Phase 1 (needs `/<topic>` endpoint + Bearer auth)
**Risk:** Medium — touches the orchestrator's outbound notifications
**Estimated diff:** ~5 files in `langgraph-cloud-agents/`, ~200 LoC

## Goal

Stop sending orchestrator events to orc-notify as a custom envelope (`event`/`thread_id`/`status`). Instead, send plain ntfy.sh-style messages to a per-instance topic (`orchestrator-main-events`, `orchestrator-free-events`) using Bearer auth. Old path (`/v1/events`) stays alive behind a feature flag for 24h, then removed.

## Context

The current sender (`langgraph-cloud-agents/app/orchestrator/notify.py`) signs an orchestrator-shaped envelope and POSTs to `/v1/events`. This blocks orc-notify from being used by anyone else — the envelope is orchestrator-only. After Phase 2, the sender emits ntfy.sh-style messages, orc-notify accepts generic pub/sub, and any external client (curl, custom scripts, future agents) can publish to the same topic.

**Per-instance topics:** the memory note `orchestrator-notify-deploy-v9-web-v4-2026-08-28` explains two-instance split (main :8000, free :8001). Each instance publishes to its own topic so cross-tier events can be de-duped visually.

## Scope

### In

1. **Provisioning flow** — on first run, orchestrator registers a topic with orc-notify (`POST /api/topics`), receives a publish token, persists it to `~/.orchestrator/secrets/orchestrator_main/orc_notify_token` (mode 0600). Idempotent: if topic + token already exist, reuse.
2. **New sender module** `langgraph-cloud-agents/app/orchestrator/notify_v2.py` — `async def notify_v2(topic, title, body, *, priority=3, tags=None, click=None) -> bool`. Translates orchestrator envelope → ntfy-style headers + body.
3. **Feature flag** `NOTIFY_V2_ENABLED` (env, default `false` in Phase 2 start, flip after 24h parallel-run, remove default after Phase 2 close).
4. **Side-by-side logger** — when both old + new paths active, log both runs with distinct `notify_path: "v1" | "v2"` fields. Detect divergence: if v2 returns success and v1 fails (or vice versa), warn.
5. **Cutover** — flip default to `true`, monitor for 24h, then delete `notify.py` old path + remove `NOTIFY_V2_ENABLED` flag.
6. **Documentation** in `docs/notifier-deploy.md` for operators: "What changed in v2", "How to manually publish from orchestrator" curl example, "Rollback procedure" if v2 misbehaves.
7. **Test** — `langgraph-cloud-agents/tests/test_notify_v2.py`. Mock orc-notify HTTP layer, assert ntfy-shaped POST, assert retries (3x with exp backoff on 5xx).

### Out

- **Removing orc-notify's `/v1/events` route** — Phase 5 (only after external clients confirm migration).
- **Telegram/email delivery from orc-notify** — out of scope.
- **Topic auto-creation on first publish** — explicit `POST /api/topics` keeps audit trail.

## Tasks (ordered)

1. Write `notify_v2.py` with the new sender. Reuse existing `httpx.AsyncClient` + signing helpers from `notify.py` where applicable.
2. Write `provision_topic.py` — one-shot script that registers topic + persists token. Idempotent.
3. Wire feature flag into `_schedule_notify` (the fire-and-forget entry point in `notify.py` or its replacement).
4. Add parallel-run logger: log both `notify_path: v1` and `notify_path: v2` events with same `event_id` for diff detection.
5. Update `.env.example` in orchestrator repo: add `ORC_NOTIFY_BASE`, `ORC_NOTIFY_TOPIC`, `ORC_NOTIFY_PUBLISH_TOKEN`, `NOTIFY_V2_ENABLED`.
6. Write `test_notify_v2.py`. Coverage: success path, 5xx retry, 401 (re-provision), 429 (backoff), network error (give up after N).
7. Run provisioning flow in dev: `python3 -m langgraph_cloud_agents.app.orchestrator.provision_topic`. Confirm token written to `~/.orchestrator/secrets/orchestrator_main/orc_notify_token`.
8. Manual smoke: trigger an orchestrator task completion, verify it appears in orc-notify via the new endpoint (curl `GET /api/topics/orchestrator-main-events/messages`).
9. Update `docs/notifier-deploy.md` (additive).
10. **Commit locally** (no push — ALWAYS-ASK gate per `publish-gate.sh`).

## Verification

### Local

```bash
cd /Volumes/SSDNSKIY/VSCODE/orchestrator
pytest langgraph-cloud-agents/tests/test_notify_v2.py -q

# Manual flow against local orc-notify (assumes orc-notify on :8000):
ORC_NOTIFY_BASE=http://localhost:8000 \
ORC_NOTIFY_TOPIC=orchestrator-test \
ORC_NOTIFY_PUBLISH_TOKEN=<from provisioning> \
NOTIFY_V2_ENABLED=true \
python3 -m langgraph_cloud_agents.app.orchestrator.notify_v2 \
  "Test title" "Test body" --priority 4 --tags test,smoke
```

Expected: 201 + message id; curl `GET http://localhost:8000/api/topics/orchestrator-test/messages` returns the message.

### Production (gated — ALWAYS-ASK)

```bash
# 1. SSH to VPS or use orchestrator's API
# 2. Run provision script for both instances:
docker exec langgraph-orchestrator-main python3 -m langgraph_cloud_agents.app.orchestrator.provision_topic
docker exec langgraph-orchestrator-free python3 -m langgraph_cloud_agents.app.orchestrator.provision_topic

# 3. Flip feature flag in env:
# Edit /captain-data/langgraph-orchestrator-main/.env → NOTIFY_V2_ENABLED=true
# Same for free.
# Captain envVar change requires appDefinitions/update + service restart.

# 4. Trigger orchestrator event; verify both v1 + v2 paths logged.
docker service logs langgraph-orchestrator-main --tail 50 | grep notify_path

# 5. 24h observation window. Then:
# - Delete old notify.py
# - Remove NOTIFY_V2_ENABLED flag from .env
# - Update deploy-graph flow to not include the flag
```

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Token leaked via logs | High | Never log token value. Only log `token_id` (first 8 chars of UUID). `secrets.token_urlsafe(32)` not used — UUIDv4 is sufficient. |
| Old + new both firing double-notifies users | Medium | During 24h parallel-run, the UI shows two notifications per event. Document this prominently. UI dedup logic in Phase 3. |
| Provisioning fails on a partial run | Low | Provisioning is idempotent. Token persists to file before any publish. Re-run on failure. |
| v2 path silently drops events on 5xx | Medium | Retry with exp backoff (3 attempts, 1s/2s/4s). After exhaustion, log + count metric, do not raise (matches existing fire-and-forget pattern). |
| Cross-instance publish lands in wrong topic | Low | Per-instance `ORC_NOTIFY_TOPIC` env var set at deploy time. `provision_topic` reads `ORCHESTRATOR_INSTANCE` env to pick name. |

## Success criteria

- [ ] `pytest langgraph-cloud-agents/tests/test_notify_v2.py -q` passes.
- [ ] Provisioning script idempotent (running twice doesn't duplicate topic).
- [ ] Parallel-run for 24h shows both `notify_path: v1` and `notify_path: v2` in logs.
- [ ] Old `notify.py` deleted + feature flag removed after 24h window.
- [ ] `langgraph-orchestrator-main` + `langgraph-orchestrator-free` env blocks contain `ORC_NOTIFY_BASE`, `ORC_NOTIFY_TOPIC`, `ORC_NOTIFY_PUBLISH_TOKEN`.
- [ ] No regressions in existing `test_notify.py`.
- [ ] `docs/notifier-deploy.md` updated.
- [ ] STATE.md updated.
