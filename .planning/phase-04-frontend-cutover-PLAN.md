# Phase 4 — Frontend cutover (drop legacy UI)

**Status:** draft (2026-09-08)
**Depends on:** Phase 3 (new SPA must be feature-complete and stable for 7 days)
**Risk:** Medium — irreversible user-facing change
**Estimated diff:** ~15 files deleted, ~3 files edited, ~150 LoC net removal

## Goal

Make the new shadcn SPA the only frontend. Delete:
- Legacy Jinja2 templates (`app/templates/*`)
- Legacy UI router (`app/routers/ui.py`)
- Legacy static assets (`app/static/*`)
- Backward-compat shim pages (`web/src/pages/_legacy/*`)
- Old SPA pages (Dashboard, Rules, Keys at top-level — replaced by Topics-centric versions)

After Phase 4, **the only frontend is the shadcn SPA served from `orc-notify-web`**. The FastAPI app serves only JSON + SSE.

## Context

This phase is the irreversible cutover. It must come after Phase 3 has proven itself stable (≥ 7 days in production with no P1 bugs). The 7-day window lets us catch:
- Edge cases in the new layout (responsive breakpoints, dark mode contrast)
- Performance regressions (slow list rendering, SSE reconnect storms)
- User friction (Cmd+K discoverability, copy-paste curl examples)

If issues surface during the 7-day window, Phase 4 is paused; Phase 3 patches ship first.

## Scope

### In

1. **Delete Jinja2 UI**:
   - Remove `app/templates/` directory entirely.
   - Remove `app/routers/ui.py` entirely.
   - Remove `app/static/` directory entirely.
   - Remove `jinja2` from `pyproject.toml` dependencies (verify no other use).
   - Remove `SessionMiddleware` flash message usage from `app/main.py` (verify no other consumer).
2. **Delete legacy SPA shim**:
   - Remove `web/src/pages/_legacy/` directory.
   - Remove `/dashboard`, `/rules` from `web/src/router.tsx` (or return 410 Gone for explicit redirects).
3. **Delete deprecated SPA pages**:
   - `web/src/pages/Dashboard.tsx`, `Rules.tsx` — remove (replaced by Topics + TopicDetail).
   - `web/src/pages/Keys.tsx` — keep as global keys view (still useful).
4. **Update nginx** — verify `web/nginx.conf` doesn't reference any deleted paths. Should be no-op.
5. **Update FastAPI CORS / static mount** — remove `/static` mount from `app/main.py:create_app()`.
6. **Add 410 Gone handlers** for any path the SPA used to serve but no longer does:
   - `/dashboard`, `/rules` → 410 with link to `/topics`.
   - Implement via nginx config OR via a small fallback route in `web/src/router.tsx` (renders `<Gone />` component).
7. **Update README** — drop "Jinja2 UI" references.
8. **Update `docs/notifier-deploy.md`** — drop references to Jinja2 templates, static files.
9. **Migration note in MEMORY** — "Phase 4 SHIPPED, Jinja2 UI removed, shadcn SPA is sole frontend."

### Out

- **Removing `/api/rules`, `/api/keys`, `/v1/events` from FastAPI** — Phase 5. External clients might still hit them; need a separate deprecation window.
- **Removing HeroUI dependencies from `web/package.json`** — should be no HeroUI deps in Phase 3 code, but verify with `pnpm why @heroui/react` and remove if stale.
- **Cleanup of duplicate Pydantic models in routers** — Phase 5 (or already done in Phase 1).

## Tasks (ordered)

1. Verify Phase 3 SPA has been in production for ≥ 7 days with no P1 bugs. Check Obsidian Kanban + orchestrator logs.
2. `pnpm why @heroui/react @heroui/styles` in `web/` — confirm zero references in current code. If clean, remove from `package.json`.
3. Delete `web/src/pages/_legacy/`. Update `web/src/router.tsx`.
4. Delete `web/src/pages/Dashboard.tsx`, `Rules.tsx`. Verify `router.tsx` no longer imports them.
5. Delete `app/templates/`, `app/static/`, `app/routers/ui.py`.
6. Remove `jinja2` from `pyproject.toml`. `pip install -e .` to verify.
7. Remove `SessionMiddleware` and `/static` mount from `app/main.py`.
8. Run `pytest tests/ -q` — all green (UI tests should be removed).
9. Run `pnpm test`, `pnpm build` — all green.
10. Update `web/src/router.tsx` to return `<Gone />` component for `/dashboard`, `/rules` paths.
11. Update `README.md` — drop Jinja2 references.
12. Update `docs/notifier-deploy.md` — drop Jinja2 references.
13. **Commit locally** (no push — publish-gate).
14. After deploy verification: write memory note `orc-notify-phase-04-cutover-2026-09-XX.md`.

## Verification

### Local

```bash
cd /Volumes/SSDNSKIY/VSCODE/orc-notify
pytest tests/ -q                # existing tests stay green
cd web && pnpm test && pnpm build
ls app/templates                # should fail: No such file or directory
ls app/static                   # should fail
ls app/routers/ui.py            # should fail
```

### Production (gated — ALWAYS-ASK)

```bash
# After deploy:
curl -I https://orc-notify-web.orc.golden-antelope.ru/dashboard
# Expect: HTTP/2 410 (Gone) or 200 with shim linking to /topics
curl https://orc-notify-web.orc.golden-antelope.ru/
# Expect: HTTP/2 200 + shadcn SPA HTML
curl https://orc-notify.orc.golden-antelope.ru/healthz
# Expect: HTTP/2 200 (backend untouched)
```

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Users with bookmarks to `/dashboard` or `/rules` see 404 | Medium | 410 Gone with redirect link to `/topics` is more friendly than 404. |
| Jinja2 templates had hidden functionality we forgot | Low | `git grep` for any imports of `app.templates` outside `ui.py` before deletion. |
| SessionMiddleware used elsewhere | Low | `git grep SessionMiddleware` should show only `main.py:49-55`. |
| Static assets referenced by external scripts (e.g., monitoring) | Low | Verify `git grep '/static/'` shows zero hits in source code. |
| Phase 3 SPA has latent bug discovered post-cutover | High | 7-day observation window before Phase 4. Emergency rollback = redeploy previous web image (Captain supports this with one click). |
| New SPA bundle ships larger than HeroUI baseline | Low | Tracked in Phase 3 success criteria. If Phase 3 didn't hit < 500 KB, defer Phase 4 until it does. |

## Success criteria

- [ ] Phase 3 SPA stable in production for ≥ 7 days.
- [ ] `app/templates/`, `app/static/`, `app/routers/ui.py` deleted.
- [ ] `pnpm why @heroui/react` shows no installation.
- [ ] `pytest tests/ -q` green.
- [ ] `pnpm test && pnpm build` green.
- [ ] `/dashboard`, `/rules` return 410 Gone with redirect link.
- [ ] `/topics` is the only UI entry point.
- [ ] Memory note written.
- [ ] STATE.md updated.
