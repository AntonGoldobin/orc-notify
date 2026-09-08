import * as React from 'react'
import { cn } from '@/lib/utils'

/** Avatar without Radix — we just display an initial / fallback. */
export const Avatar = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-muted', className)}
      {...props}
    />
  ),
)
Avatar.displayName = 'Avatar'

export const AvatarFallback = React.forwardRef<HTMLSpanElement, React.HTMLAttributes<HTMLSpanElement>>(
  ({ className, ...props }, ref) => (
    <span
      ref={ref}
      className={cn('flex h-full w-full items-center justify-center rounded-full bg-muted text-xs font-medium', className)}
      {...props}
    />
  ),
)
AvatarFallback.displayName = 'AvatarFallback'