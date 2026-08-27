import type { HistoryOut, SseNotification, SseReady } from './types'

export interface HistoryParams {
  since?: string
  limit?: number
}

export async function history({ since, limit }: HistoryParams = {}): Promise<HistoryOut[]> {
  const qs = new URLSearchParams()
  if (since) qs.set('since', since)
  if (limit !== undefined) qs.set('limit', String(limit))
  const path = qs.toString() ? `/api/events?${qs}` : '/api/events'
  const res = await fetch(path, { credentials: 'include' })
  if (!res.ok) {
    const detail = await res.json().catch(() => res.statusText)
    throw new Error(`history ${res.status}: ${JSON.stringify(detail)}`)
  }
  return res.json() as Promise<HistoryOut[]>
}

export type SseEvent =
  | { type: 'ready'; data: SseReady }
  | { type: 'notification'; data: SseNotification }
  | { type: 'ping' }
  | { type: 'error'; error: Event }

export interface SseHandle {
  close: () => void
}

/**
 * Subscribe to /api/events/sse. Returns a handle whose `close()` stops the stream.
 * The listener receives typed events; `ping` events are emitted for heartbeat
 * (currently unused by the UI but available for reconnection logic).
 */
export function subscribe(listener: (event: SseEvent) => void): SseHandle {
  const es = new EventSource('/api/events/sse', { withCredentials: true })

  es.addEventListener('ready', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data) as SseReady
      listener({ type: 'ready', data })
    } catch (err) {
      listener({ type: 'error', error: err as Event })
    }
  })

  es.addEventListener('notification', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data) as SseNotification
      listener({ type: 'notification', data })
    } catch (err) {
      listener({ type: 'error', error: err as Event })
    }
  })

  es.addEventListener('ping', () => {
    listener({ type: 'ping' })
  })

  es.onerror = (e) => {
    listener({ type: 'error', error: e })
  }

  return {
    close: () => es.close(),
  }
}
