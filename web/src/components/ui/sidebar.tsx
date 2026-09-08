import * as React from 'react'
import { PanelLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SidebarContextValue {
  collapsed: boolean
  setCollapsed: (v: boolean) => void
}

const SidebarContext = React.createContext<SidebarContextValue | null>(null)

export function SidebarProvider({
  defaultCollapsed = false,
  children,
}: {
  defaultCollapsed?: boolean
  children: React.ReactNode
}) {
  const [collapsed, setCollapsed] = React.useState(defaultCollapsed)
  return (
    <SidebarContext.Provider value={{ collapsed, setCollapsed }}>
      <div className="flex min-h-svh w-full">{children}</div>
    </SidebarContext.Provider>
  )
}

export function Sidebar({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const ctx = React.useContext(SidebarContext)
  if (!ctx) throw new Error('Sidebar must be inside <SidebarProvider>')
  return (
    <aside
      className={cn(
        'flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all',
        ctx.collapsed ? 'w-14' : 'w-56',
        className,
      )}
      {...props}
    >
      {children}
    </aside>
  )
}

export function SidebarHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex items-center gap-2 px-4 py-3 border-b border-sidebar-border', className)} {...props} />
}

export function SidebarContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex-1 overflow-y-auto py-2', className)} {...props} />
}

export function SidebarFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border-t border-sidebar-border px-2 py-2', className)} {...props} />
}

export function SidebarTrigger({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const ctx = React.useContext(SidebarContext)
  if (!ctx) throw new Error('SidebarTrigger must be inside <SidebarProvider>')
  return (
    <button
      type="button"
      onClick={() => ctx.setCollapsed(!ctx.collapsed)}
      aria-label="Toggle sidebar"
      className={cn('inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent', className)}
      {...props}
    >
      <PanelLeft className="h-4 w-4" />
    </button>
  )
}

interface SidebarMenuProps extends React.HTMLAttributes<HTMLDivElement> {}

export function SidebarMenu({ className, ...props }: SidebarMenuProps) {
  return <nav className={cn('flex flex-col gap-1 px-2', className)} {...props} />
}

export function SidebarMenuItem({
  className,
  active,
  children,
}: {
  className?: string
  active?: boolean
  children: React.ReactNode
}) {
  return (
    <div
      data-active={active ? 'true' : undefined}
      className={cn(
        'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
        active && 'bg-sidebar-accent text-sidebar-accent-foreground font-medium',
        className,
      )}
    >
      {children}
    </div>
  )
}