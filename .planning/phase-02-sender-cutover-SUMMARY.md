# Phase 2 — Orchestrator sender cutover — SUMMARY

**Status:** pending (created 2026-09-08, draft)

## What shipped

_Pending Phase 2 execution._

## Verification evidence

_Pending._

### Test counts

| Suite | Before | After |
|---|---|---|
| `tests/test_notify.py` (existing) | ? | ? |
| `tests/test_notify_v2.py` (NEW) | — | ? |
| **Total orchestrator tests** | ? | ? |

### Parallel-run log samples (24h window)

```
_Paste docker service logs grepped for notify_path here._
```

## Files

_Pending._

| File | Action | LoC |
|---|---|---|
| `langgraph-cloud-agents/app/orchestrator/notify_v2.py` | NEW | ? |
| `langgraph-cloud-agents/app/orchestrator/provision_topic.py` | NEW | ? |
| `langgraph-cloud-agents/app/orchestrator/notify.py` | EDIT (feature flag) | ? |
| `langgraph-cloud-agents/tests/test_notify_v2.py` | NEW | ? |
| `langgraph-cloud-agents/.env.example` | EDIT | ? |

## Open follow-ups

- [ ] Phase 3 — frontend shadcn scaffold
- [ ] Phase 5 — remove `/v1/events` route after Phase 2 + 24h parallel-run verified
- [ ] Update `docs/notifier-deploy.md` with provisioning procedure
