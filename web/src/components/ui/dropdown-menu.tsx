import * as React from 'react'
import { cn } from '@/lib/utils'

interface DropdownContextValue {
  open: boolean
  setOpen: (v: boolean) => void
}

const DropdownContext = React.createContext<DropdownContextValue | null>(null)

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)
  return (
    <DropdownContext.Provider value={{ open, setOpen }}>
      <div className="relative inline-block">{children}</div>
    </DropdownContext.Provider>
  )
}

export function DropdownMenuTrigger({
  asChild,
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) {
  const ctx = React.useContext(DropdownContext)
  if (!ctx) throw new Error('DropdownMenuTrigger must be inside <DropdownMenu>')
  return (
    <button
      type="button"
      onClick={() => ctx.setOpen(!ctx.open)}
      aria-expanded={ctx.open}
      className={cn(className)}
      {...props}
    >
      {children}
    </button>
  )
}

export function DropdownMenuContent({
  align = 'start',
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { align?: 'start' | 'end' | 'center' }) {
  const ctx = React.useContext(DropdownContext)
  if (!ctx) throw new Error('DropdownMenuContent must be inside <DropdownMenu>')
  if (!ctx.open) return null
  return (
    <div
      role="menu"
      className={cn(
        'absolute z-50 mt-2 min-w-[10rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md',
        align === 'end' ? 'right-0' : align === 'center' ? 'left-1/2 -translate-x-1/2' : 'left-0',
        className,
      )}
      {...props}
    />
  )
}

export function DropdownMenuItem({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { inset?: boolean }) {
  const ctx = React.useContext(DropdownContext)
  return (
    <div
      role="menuitem"
      onClick={(e) => {
        props.onClick?.(e)
        ctx?.setOpen(false)
      }}
      className={cn(
        'relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent',
        className,
      )}
      {...props}
    />
  )
}

export function DropdownMenuSeparator({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('-mx-1 my-1 h-px bg-muted', className)} {...props} />
}

export function DropdownMenuLabel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-2 py-1.5 text-sm font-semibold', className)} {...props} />
}