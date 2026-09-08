# Phase 3 — Frontend shadcn scaffold + topic pages

**Status:** draft (2026-09-08)
**Depends on:** Phase 1 (needs `/api/topics`, `/api/topics/{name}/keys`, `/api/topics/{name}/messages` JSON endpoints)
**Risk:** Medium-High — biggest UI rewrite in the project
**Estimated diff:** ~30 files in `web/`, ~2500 LoC

## Goal

Replace the HeroUI v3 SPA with a shadcn/ui-based SPA organised around topics. After this phase, the UI shows:
- Topics grid on the dashboard (`/topics`)
- Topic detail with Messages / Publish / Settings tabs (`/topics/:name`)
- Cmd+K command palette for fast topic switching
- Sidebar layout with shadcn `<Sidebar>` primitives

The OLD pages (`/dashboard`, `/rules`, `/keys`) keep working via a redirect shim — the URL changes but the old paths still resolve until Phase 4 cutover.

## Context

Current `web/` is React 19 + Vite 8 + HeroUI v3 + Tailwind v4. HeroUI v3 has 8 known gotchas (`orc-notify-web-react-heroui-r1-2026-08-27` memory note) and an opaque minor-version story. shadcn/ui gives us copy-paste control: components live in our repo, can be patched in-place, no surprise breakage. Same Tailwind v4 stays.

**Why shadcn, not a maintained library:** orc-notify is a utility dashboard with custom layouts (Cmd+K, message virtualization). A library forces opinions; shadcn gives primitives we compose.

## Scope

### In

1. **shadcn/ui initialization** — `pnpm dlx shadcn@latest init` against existing `web/`. Configure Tailwind v4 (already in place), set base color to `slate` + `zinc` accents, dark mode `class` strategy.
2. **shadcn primitives added** to `web/src/components/ui/`:
   - `button`, `input`, `textarea`, `label`, `select`, `switch`, `checkbox`
   - `card`, `table`, `badge`, `separator`, `scroll-area`
   - `sidebar` (composite of primitives — `SidebarProvider`, `SidebarTrigger`, etc.)
   - `dialog`, `dropdown-menu`, `tabs`, `tooltip`
   - `sonner` (toast)
   - `command` (cmdk wrapped)
   - `skeleton`, `avatar`, `hover-card`
   - `form` (react-hook-form + zod resolver)
3. **Dependencies added** to `web/package.json`:
   - `lucide-react` (icons)
   - `sonner` (toast)
   - `cmdk` (command palette)
   - `react-hook-form`, `@hookform/resolvers`, `zod`
   - `date-fns` (relative time formatting)
   - `class-variance-authority`, `clsx`, `tailwind-merge` (shadcn standard)
4. **API client modules** in `web/src/api/`:
   - `topics.ts` — `listTopics`, `getTopic`, `createTopic`, `updateTopic`, `deleteTopic`
   - `topic-keys.ts` — `listKeys`, `createKey`, `rotateKey`, `deleteKey`
   - `messages.ts` — `listMessages(topic, { since?, until?, limit? })`
   - `publish.ts` — `publishMessage(topic, { title, body, priority, tags, click })`
   - `events-sse.ts` — wraps native `EventSource` for `/api/topics/:name/sse`
5. **React Query hooks** in `web/src/hooks/`:
   - `useTopics`, `useTopic`, `useCreateTopic`, `useUpdateTopic`, `useDeleteTopic`
   - `useTopicKeys`, `useCreateTopicKey`, `useRotateTopicKey`, `useDeleteTopicKey`
   - `useMessages` (infinite query with `since` cursor)
   - `usePublishMessage`
   - `useLiveMessages` (subscribes to SSE, prepends to query cache)
6. **Layout shell** — `web/src/layouts/AppLayout.tsx`:
   - `<SidebarProvider>` + `<AppSidebar>` + `<SidebarInset>` (topbar + main pane)
   - Topbar: logo, `<CommandTrigger>` (Cmd+K hint), `<UserMenu>`
   - Footer (status line): SSE connection indicator
7. **Pages** in `web/src/pages/`:
   - `Topics.tsx` — grid of topic cards (name, last activity, unread badge, sparkline)
   - `TopicDetail.tsx` — `<Tabs>` with three tabs:
     - `Messages.tsx` — virtualized list (use `react-virtuoso` or `tanstack/react-virtual`) + live SSE tail
     - `Publish.tsx` — copy-paste curl example (one-click copy) + simple test form
     - `Settings.tsx` — rename, default priority, manage keys (table + create modal), danger zone (delete)
   - `Keys.tsx` — global keys view across all topics (rename of old `/keys`)
   - `Docs.tsx` — auto-generated per-topic curl examples + general API reference
   - `Settings.tsx` — profile + change password (kept from old SPA)
   - `auth/Login.tsx`, `auth/Register.tsx`, `auth/Reset.tsx` (kept, restyled to shadcn)
   - `Root.tsx` — auth-aware redirect (kept)
   - `NotFound.tsx` — 404 (kept)
8. **Theme toggle** — `web/src/components/ThemeToggle.tsx` — dark / light / system via `class` on `<html>`. Uses `sonner` for toasts.
9. **Route map** — `web/src/router.tsx`:
   - `/` → redirect to `/topics`
   - `/topics` → Topics
   - `/topics/:name` → TopicDetail (default tab = Messages)
   - `/topics/:name/:tab` → TopicDetail with explicit tab
   - `/topics/:name/keys` → redirect to `/topics/:name?tab=settings` (deep link compatibility)
   - `/keys` → global Keys (kept for backward compat with old URLs)
   - `/docs`, `/settings` → kept
   - `/login`, `/register`, `/reset` → kept
10. **Tests** — vitest unit tests for:
    - API client modules (one file per module)
    - React Query hooks (with MSW handlers)
    - Page components (smoke render with `<AppLayout>` provider)
    - Cmd+K palette (interaction test)
    - SSE handler (mock EventSource)
    Playwright E2E:
    - `auth.spec.ts` (kept from old SPA, updated selectors)
    - `topics-happy-path.spec.ts` (new) — register → create topic → publish via UI → see in messages tab
    - `topic-keys.spec.ts` (new) — create key, copy secret, rotate, delete
11. **Backward-compat shim** — `web/src/pages/_legacy/Dashboard.tsx` renders old page with a deprecation banner pointing to `/topics`. Route at `/dashboard` shows the shim.
12. **Bundle size check** — `web/vite.config.ts` with `rollup-plugin-visualizer`. Target: < 500 KB JS gzipped (down from 647 KB HeroUI baseline).
13. **Update `web/nginx.conf`** — no functional change, just verify SPA fallback still routes to `index.html`.
14. **Update `web/Dockerfile`** — no change needed.
15. **Documentation** in `web/README.md` (new file) — shadcn primitives in use, theme tokens, how to add a new primitive.

### Out

- **Removing old pages** — Phase 4 (cutover). Old `/dashboard`, `/rules`, `/keys` get the shim now and are removed later.
- **Removing Jinja2 templates** — Phase 4.
- **Custom dark-mode color tokens** — use shadcn defaults; customize later if needed.
- **i18n** — not in scope.
- **Mobile-first redesign** — desktop-first; mobile responsive as side-effect.

## Tasks (ordered)

1. Initialize shadcn: `pnpm dlx shadcn@2 init` in `web/`. Configure Tailwind v4 compatibility.
2. Add `web/src/components/ui/` primitives in this order: button, input, label, card, badge → separator, scroll-area → sidebar → dialog, dropdown-menu, tabs → command, sonner → form.
3. Add dependencies (lucide-react, sonner, cmdk, react-hook-form, @hookform/resolvers, zod, date-fns, class-variance-authority, clsx, tailwind-merge).
4. Write API client modules (`api/topics.ts`, `api/topic-keys.ts`, `api/messages.ts`, `api/publish.ts`).
5. Write React Query hooks.
6. Write `AppLayout.tsx` with sidebar + topbar.
7. Write `Topics.tsx` (grid).
8. Write `TopicDetail.tsx` skeleton + three tab components.
9. Write `Messages.tsx` with virtualization + SSE integration.
10. Write `Publish.tsx` with curl example generator.
11. Write `Settings.tsx` (topic) with key management.
12. Write `Keys.tsx` global, `Docs.tsx`, `Settings.tsx` profile.
13. Write auth pages (Login, Register, Reset) — restyled with shadcn primitives.
14. Update `router.tsx` with new routes + redirect shims.
15. Write tests (vitest + Playwright).
16. Run `pnpm test` + `pnpm build` + `pnpm e2e`. All green.
17. Bundle size audit — `pnpm build` output, confirm < 500 KB JS gzipped.
18. Manual visual review at `pnpm dev` against local backend.
19. Update `web/README.md`.
20. **Commit locally** (no push — publish-gate).

## Verification

### Local

```bash
cd /Volumes/SSDNSKIY/VSCODE/orc-notify/web
pnpm install
pnpm exec shadcn@latest init   # if not done in step 1
pnpm test                       # vitest, must stay green
pnpm build                      # bundle size audit
pnpm e2e                        # Playwright (requires backend on :8000)
pnpm dev                        # manual UI review
```

### Production (gated — ALWAYS-ASK)

Deploy via `services.yaml` `orc-notify-web` (after Phase 3 ships a new `web/` image). Smoke:
- `https://orc-notify-web.orc.golden-antelope.ru/` → 200 + new SPA HTML
- JS bundle hash matches local build
- Login with existing user → lands on `/topics`
- Create topic, see it in grid, drill in, publish via UI, see in messages tab

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| shadcn primitives break on Tailwind v4 upgrade | Medium | Pin Tailwind v4 minor at scaffold. shadcn docs are v4-compatible as of 2026. |
| Bundle size regression (shadcn + Tailwind v4 utilities) | Medium | Use `pnpm build --analyze`. Tree-shake icons. Lazy-load Dialog/DropdownMenu. |
| SSE reconnect storms on flaky networks | Medium | Backoff in `useLiveMessages` (1s, 2s, 4s, max 30s). Heartbeat-based dead connection detection. |
| Old `/dashboard` URL bookmarks break | Low | Shim page at `/dashboard` with deprecation banner. Removed in Phase 4. |
| HeroUI v3 + shadcn dual stack for a few weeks | Medium | Two parallel CSS pipelines until Phase 4 cutover. Acceptable — different routes, no class collision. |
| Cmd+K shortcut conflict with browser shortcuts | Low | Test on Chrome, Safari, Firefox. Use `meta+k` on Mac, `ctrl+k` on Win/Linux. |
| New dependency `react-hook-form` adds 30 KB | Low | Already plan to track; deferred to bundle audit step 17. |

## Success criteria

- [ ] `pnpm test` green (existing 24 vitest + ≥ 20 new specs).
- [ ] `pnpm e2e` green (existing 2 Playwright + ≥ 2 new specs).
- [ ] `pnpm build` produces bundle < 500 KB JS gzipped.
- [ ] All 5 new pages render correctly (Topics, TopicDetail tabs, Keys, Docs, Settings).
- [ ] Cmd+K opens palette, fuzzy-searches topics, jumps correctly.
- [ ] SSE live tail works (publish → row appears in < 1s).
- [ ] Deprecation banner on `/dashboard` shim.
- [ ] `web/README.md` documents shadcn primitives in use.
- [ ] STATE.md updated.
