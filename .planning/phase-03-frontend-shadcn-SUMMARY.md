# Phase 3 — Frontend shadcn scaffold + topic pages — SUMMARY

**Status:** pending (created 2026-09-08, draft)

## What shipped

_Pending Phase 3 execution._

## Verification evidence

_Pending._

### Test counts

| Suite | Before | After |
|---|---|---|
| `web/src/api/*.test.ts` (NEW) | — | ? |
| `web/src/hooks/*.test.ts` (NEW) | — | ? |
| `web/src/pages/*.test.tsx` (NEW) | — | ? |
| `web/e2e/topics-happy-path.spec.ts` (NEW) | — | ? |
| `web/e2e/topic-keys.spec.ts` (NEW) | — | ? |
| Existing vitest specs | 24 | 24 (kept) |
| Existing Playwright specs | 2 | 2 (kept) |
| **Total** | **26** | **≥ 50** |

### Bundle size

| Asset | Before (HeroUI) | After (shadcn) |
|---|---|---|
| JS gzipped | 647 KB | _pending — target < 500 KB_ |
| CSS gzipped | 416 KB | _pending_ |

### Visual verification

_Paste screenshots / describe manual review notes here._

## Files

_Pending._

| File | Action | LoC |
|---|---|---|
| `web/src/components/ui/*` | NEW (~25 files) | ~? |
| `web/src/pages/Topics.tsx` | NEW | ? |
| `web/src/pages/TopicDetail.tsx` | NEW | ? |
| `web/src/pages/TopicMessages.tsx` | NEW | ? |
| `web/src/pages/TopicPublish.tsx` | NEW | ? |
| `web/src/pages/TopicSettings.tsx` | NEW | ? |
| `web/src/pages/_legacy/Dashboard.tsx` | NEW (shim) | ? |
| `web/src/layouts/AppLayout.tsx` | NEW | ? |
| `web/src/api/{topics,topic-keys,messages,publish}.ts` | NEW (4 files) | ? |
| `web/src/hooks/*.ts` | NEW | ? |
| `web/src/router.tsx` | EDIT | ? |
| `web/package.json` | EDIT | ? |
| `web/README.md` | NEW | ? |

## Open follow-ups

- [ ] Phase 4 — frontend cutover (remove shim, drop Jinja2)
- [ ] Bundle size audit (target < 500 KB JS)
- [ ] Document shadcn theme tokens in Obsidian / DESIGN.md
