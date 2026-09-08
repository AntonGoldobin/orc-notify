# Phase 4 — Frontend cutover (drop legacy UI) — SUMMARY

**Status:** pending (created 2026-09-08, draft)

## What shipped

_Pending Phase 4 execution._

## Verification evidence

_Pending._

### Production curls

```
_Paste curl outputs here._
```

### Files removed

_Pending._

| Path | Reason |
|---|---|
| `app/templates/` | Jinja2 UI replaced by SPA |
| `app/static/` | Jinja2 UI replaced by SPA |
| `app/routers/ui.py` | Jinja2 UI replaced by SPA |
| `web/src/pages/_legacy/` | Backward-compat shim, no longer needed |
| `web/src/pages/Dashboard.tsx` | Replaced by `/topics` |
| `web/src/pages/Rules.tsx` | Replaced by `/topics/:name` settings tab |
| `pyproject.toml` (jinja2 dep) | No other consumer |

## Files edited

_Pending._

| Path | Change |
|---|---|
| `app/main.py` | Remove `SessionMiddleware`, `/static` mount, `ui` router |
| `pyproject.toml` | Drop `jinja2` |
| `web/src/router.tsx` | Remove Dashboard/Rules routes, add 410 Gone handler |
| `web/package.json` | Drop HeroUI deps |
| `README.md` | Drop Jinja2 references |
| `docs/notifier-deploy.md` | Drop Jinja2 references |

## Open follow-ups

- [ ] Phase 5 — final cleanup (drop old API routes, duplicate Pydantic, channel column, in_app_notifications table)
- [ ] Emergency rollback procedure documented in MEMORY
