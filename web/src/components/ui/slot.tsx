import * as React from 'react'
import { cn } from '@/lib/utils'

export interface SlotProps extends React.HTMLAttributes<HTMLElement> {
  children?: React.ReactNode
}

/**
 * Slot — minimal polymorphic-as-child primitive (shadcn convention).
 * Merges its own props onto the first child via React.cloneElement so
 * Tailwind utilities + event handlers compose without an extra runtime dep.
 */
export const Slot = React.forwardRef<HTMLElement, SlotProps>(({ children, ...slotProps }, ref) => {
  if (!React.isValidElement(children)) return null
  const childProps = (children.props ?? {}) as Record<string, unknown>
  const mergedProps: Record<string, unknown> = { ...slotProps, ...childProps }
  if (slotProps.className || childProps.className) {
    mergedProps.className = cn(slotProps.className as string | undefined, childProps.className as string | undefined)
  }
  const childRef = (children as unknown as { ref?: React.Ref<HTMLElement> }).ref
  if (ref && childRef) {
    mergedProps.ref = (node: HTMLElement) => {
      ;(ref as React.MutableRefObject<HTMLElement | null>).current = node
      if (typeof childRef === 'function') childRef(node)
      else if (childRef && 'current' in (childRef as object)) {
        ;(childRef as React.MutableRefObject<HTMLElement | null>).current = node
      }
    }
  } else if (ref) {
    mergedProps.ref = ref
  }
  return React.cloneElement(children, mergedProps as React.Attributes)
})
Slot.displayName = 'Slot'