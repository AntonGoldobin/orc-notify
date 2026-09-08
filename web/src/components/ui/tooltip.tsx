import * as React from 'react'
import { cn } from '@/lib/utils'

/** Tooltip via title attribute (no Radix dep). Good enough for keyboard a11y. */
export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

export function Tooltip({
  content,
  children,
  className,
}: {
  content: React.ReactNode
  children: React.ReactElement
  className?: string
}) {
  const child = React.Children.only(children) as React.ReactElement<{ title?: string; className?: string }>
  const cls = cn(child.props.className, className)
  return React.cloneElement(child, { title: typeof content === 'string' ? content : undefined, className: cls })
}