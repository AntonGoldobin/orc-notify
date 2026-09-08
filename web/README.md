# orc-notify-web — shadcn/ui SPA

React 19 + Vite 8 + TypeScript 6 + Tailwind v4 + shadcn/ui primitives + React Query.

## Stack

| Layer | Library | Notes |
|---|---|---|
| Build | Vite 8 + `@vitejs/plugin-react` | Type-check via `tsc -b` |
| Styling | Tailwind v4 + shadcn tokens | shadcn-style CSS variables (`--background`, `--foreground`, `--primary`, etc.) — slate palette + dark `class` strategy |
| Primitives | shadcn/ui (vendored) | Lives in `src/components/ui/`. Not a package — copy-paste, can patch in place. |
| Icons | `lucide-react` | |
| State (server) | `@tanstack/react-query` 5.102.7 | |
| Toasts | `sonner` | |
| Command palette | `cmdk` | Cmd+K opens topic picker |
| Routing | `react-router-dom` 7 | |
| Tests | Vitest 4 + Testing Library | `pnpm test` |
| E2E | Playwright 1.62 | `pnpm e2e` (requires backend on :8000) |

## shadcn primitives in use

All live in `src/components/ui/`:

- `button` (cva: `default | destructive | outline | secondary | ghost | link`, sizes `default | sm | lg | icon`)
- `input`, `textarea`, `label`
- `card` (split: `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`)
- `badge` (`default | secondary | destructive | outline`)
- `tabs` (composite `<Tabs>` + `<TabsList>` + `<TabsTrigger>` + `<TabsContent>`)
- `dialog` (controlled, with `DialogTitle` for a11y)
- `dropdown-menu` (custom, no Radix dep)
- `sidebar` (composite: `SidebarProvider` + `Sidebar` + `SidebarHeader/Content/Footer` + `SidebarMenu` + `SidebarMenuItem` + `SidebarTrigger`)
- `select` (native `<select>` styled)
- `switch` (no Radix, button role)
- `checkbox` (no Radix, button role)
- `table` (`Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`)
- `scroll-area` (native scroll)
- `separator`
- `skeleton`
- `avatar` (no Radix)
- `tooltip` (title-attr based)
- `sonner` (Toaster re-export)
- `command` (cmdk wrapped — `Command`, `CommandInput`, `CommandList`, `CommandGroup`, `CommandItem`, `CommandEmpty`, `CommandSeparator`)

> **Why no Radix?** Each primitive is a few dozen LoC. For a 5-component admin dashboard
> the dep cost (bundle size + version drift risk) outweighs the a11y win. The Dialog
> already renders the title for screen readers; Switch/Checkbox use `role="switch"`/`role="checkbox"`.

## Theme

Slate base + dark `class` strategy. `useTheme()` reads `localStorage.app-theme` ∈ `{light, dark, system}`,
resolves to one of `light` / `dark`, and toggles `.dark` on `<html>`. The pre-paint inline
script in `index.html` applies the same logic before React mounts to avoid FOUC.

## Adding a new primitive

```bash
# Either copy the official shadcn template from ui.shadcn.com into
# src/components/ui/<name>.tsx, OR write your own ~30-LoC version.
# All primitives consume tokens from src/index.css :root.
```

After adding, update the table above.

## Scripts

| Command | Purpose |
|---|---|
| `pnpm dev` | Vite dev server on :5173 (proxies `/auth`, `/api`, `/v1` to :8000) |
| `pnpm build` | Type-check + production build → `dist/` |
| `pnpm test` | Vitest unit tests |
| `pnpm e2e` | Playwright E2E (backend must be running) |
| `pnpm typecheck` | `tsc -b --noEmit` |

## Routes (Phase 3)

```
/                         → redirect to /topics (authed) or /login (anon)
/login, /register, /reset → auth pages (shadcn Card + form)
/topics                   → Topics grid (cards: name, description, priority, retention)
/topics/:name             → TopicDetail default tab = Messages
/topics/:name/publish     → TopicDetail → Publish tab (form + curl example)
/topics/:name/settings    → TopicDetail → Settings tab (rename, priority, retention, keys)
/keys                     → global cross-topic keys view (legacy compat)
/settings                 → profile (change password, log out)
/dashboard                → legacy shim with deprecation banner (Phase 4 cutover)
```

## Bundle

Latest build:

| File | Raw | Gzipped |
|---|---|---|
| `dist/index.html` | 1.36 KB | 0.67 KB |
| `dist/assets/index.css` | 30.53 KB | 6.45 KB |
| `dist/assets/index.js` | 484.28 KB | **147.52 KB** |

Target was `< 500 KB gzipped` — comfortably under.