import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatRelative(date: Date | string | number): string {
  const d = typeof date === 'object' ? date : new Date(date)
  const diffMs = d.getTime() - Date.now()
  const absMs = Math.abs(diffMs)
  const sec = Math.round(absMs / 1000)
  const min = Math.round(sec / 60)
  const hr = Math.round(min / 60)
  const day = Math.round(hr / 24)
  const fmt = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  if (sec < 60) return fmt.format(diffMs < 0 ? -sec : sec, 'second')
  if (min < 60) return fmt.format(diffMs < 0 ? -min : min, 'minute')
  if (hr < 24) return fmt.format(diffMs < 0 ? -hr : hr, 'hour')
  return fmt.format(diffMs < 0 ? -day : day, 'day')
}