import * as React from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Bell, ChevronsUpDown, KeyRound, LogOut, Moon, Plus, Search, Settings, Sun, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarMenu, SidebarMenuItem, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Toaster } from '@/components/ui/sonner'
import { useAuth } from '@/auth/AuthProvider'
import { useTopics } from '@/hooks/useTopics'
import { toast } from 'sonner'

type Theme = 'light' | 'dark' | 'system'
const THEME_KEY = 'app-theme'

function applyTheme(theme: Theme) {
  const resolved =
    theme === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : theme
  const el = document.documentElement
  el.classList.remove('light', 'dark')
  el.classList.add(resolved)
  el.dataset.appTheme = resolved
}

function useTheme() {
  const [theme, setTheme] = React.useState<Theme>(() => {
    const saved = localStorage.getItem(THEME_KEY) as Theme | null
    return saved ?? 'system'
  })
  React.useEffect(() => {
    localStorage.setItem(THEME_KEY, theme)
    applyTheme(theme)
  }, [theme])
  React.useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme('system')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])
  return { theme, setTheme }
}

/** Toast handler used after mutations. Centralised so future telemetry hooks live in one place. */
export function notify(message: string) {
  toast.success(message)
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Theme">
          {theme === 'dark' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => setTheme('light')}>Light</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme('dark')}>Dark</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme('system')}>System</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const onLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }
  if (!user) return null
  const initial = user.email.charAt(0).toUpperCase()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="gap-2 px-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-xs font-medium">
            {initial}
          </span>
          <span className="hidden sm:inline text-sm">{user.email}</span>
          <ChevronsUpDown className="h-3 w-3 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{user.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate('/settings')}>
          <Settings className="h-4 w-4 mr-2" /> Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onLogout}>
          <LogOut className="h-4 w-4 mr-2" /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

interface SseStatusProps {
  status: 'connecting' | 'open' | 'reconnecting' | 'closed'
}

function SseStatus({ status }: SseStatusProps) {
  const tone =
    status === 'open' ? 'bg-emerald-500' : status === 'reconnecting' ? 'bg-amber-500' : 'bg-zinc-400'
  const label = status === 'open' ? 'Live' : status === 'reconnecting' ? 'Reconnecting' : 'Offline'
  return (
    <span className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className={`inline-block h-2 w-2 rounded-full ${tone}`} aria-hidden />
      SSE {label}
    </span>
  )
}

/**
 * Footer SSE indicator — driven by window 'sse-status' events dispatched from
 * TopicDetail's EventSource lifecycle (open on `ready` / `subscribe` start,
 * closed on `error` / unmount). No context/provider — one tiny global side-
 * channel, scoped to this layout.
 */
function FooterSseStatus() {
  const [status, setStatus] = React.useState<'open' | 'closed'>('closed')
  React.useEffect(() => {
    const onStatus = (e: Event) => {
      const next = (e as CustomEvent<'open' | 'closed'>).detail
      setStatus(next === 'open' ? 'open' : 'closed')
    }
    window.addEventListener('sse-status', onStatus)
    return () => window.removeEventListener('sse-status', onStatus)
  }, [])
  return <SseStatus status={status} />
}

function PaletteBody({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const { data: topics } = useTopics()
  return (
    <Command>
      <CommandInput placeholder="Jump to a topic…" />
      <CommandList>
        <CommandEmpty>No topics yet.</CommandEmpty>
        <CommandGroup heading="Topics">
          {(topics ?? []).map((t) => (
            <CommandItem
              key={t.id}
              value={t.name}
              onSelect={() => {
                navigate(`/topics/${encodeURIComponent(t.name)}`)
                onClose()
              }}
            >
              <Bell className="h-4 w-4 mr-2 opacity-70" />
              {t.name}
              <span className="ml-auto text-xs opacity-60">p{t.default_priority}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Navigation">
          <CommandItem
            value="keys"
            onSelect={() => {
              navigate('/keys')
              onClose()
            }}
          >
            <KeyRound className="h-4 w-4 mr-2 opacity-70" /> Keys
          </CommandItem>
          <CommandItem
            value="settings"
            onSelect={() => {
              navigate('/settings')
              onClose()
            }}
          >
            <Settings className="h-4 w-4 mr-2 opacity-70" /> Settings
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </Command>
  )
}

/**
 * Bridge: header button fires `cmdk:open`; we listen for it and mount the
 * global Cmd+K palette. Also binds the keyboard shortcut.
 */
function CommandPaletteOpener() {
  const [open, setOpen] = React.useState(false)

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    const onCustom = () => setOpen(true)
    window.addEventListener('keydown', onKey)
    window.addEventListener('cmdk:open', onCustom)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('cmdk:open', onCustom)
    }
  }, [])

  if (!open) return null
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="overflow-hidden p-0 max-w-xl">
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <PaletteBody onClose={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}

export function AppLayout() {
  const navigate = useNavigate()
  const { status: authStatus } = useAuth()

  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader>
          <Link to="/topics" className="flex items-center gap-2 font-semibold">
            <Zap className="h-4 w-4" />
            <span>orc-notify</span>
          </Link>
        </SidebarHeader>
        <SidebarContent>
          <SidebarMenu>
            <NavItem to="/topics" icon={<Bell className="h-4 w-4" />} label="Topics" />
            <NavItem to="/keys" icon={<KeyRound className="h-4 w-4" />} label="Keys" />
            <NavItem to="/settings" icon={<Settings className="h-4 w-4" />} label="Settings" />
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter>
          <SidebarTrigger />
        </SidebarFooter>
      </Sidebar>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b px-4 py-2">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-muted-foreground"
              onClick={() => window.dispatchEvent(new CustomEvent('cmdk:open'))}
            >
              <Search className="h-3.5 w-3.5" />
              <span>Jump to…</span>
              <kbd className="ml-2 rounded border bg-muted px-1.5 text-[10px] font-mono">⌘K</kbd>
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => navigate('/topics?new=1')}>
              <Plus className="h-4 w-4 mr-1" /> New topic
            </Button>
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>

        <main className="flex-1 px-4 py-6">
          {authStatus === 'loading' ? (
            <div className="flex justify-center py-12 text-muted-foreground">Loading…</div>
          ) : (
            <Outlet />
          )}
        </main>

        <footer className="border-t px-4 py-2">
          <div className="flex items-center justify-between">
            <FooterSseStatus />
            <Badge variant="outline" className="font-mono text-[10px]">
              v3 · shadcn
            </Badge>
          </div>
        </footer>
      </div>

      <CommandPaletteOpener />
      <Toaster />
    </SidebarProvider>
  )
}

function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink to={to} end>
      {({ isActive }) => (
        <SidebarMenuItem active={isActive} className="cursor-pointer">
          {icon}
          <span className="truncate">{label}</span>
        </SidebarMenuItem>
      )}
    </NavLink>
  )
}