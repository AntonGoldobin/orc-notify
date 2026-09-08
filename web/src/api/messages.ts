import type { MessageOut } from './types'

export interface MessagesParams {
  since?: number
  limit?: number
}

/**
 * Fetch messages for a topic via ntfy.sh-style `GET /{topic}/json?since=<epoch>`.
 * No `/api/topics/{name}/messages` endpoint exists — messages live on the topic's
 * own /json endpoint (per app/routers/subscribe.py).
 */
export async function listMessages(topic: string, params: MessagesParams = {}): Promise<MessageOut[]> {
  const qs = new URLSearchParams()
  if (params.since !== undefined) qs.set('since', String(params.since))
  if (params.limit !== undefined) qs.set('limit', String(params.limit))
  const path = qs.toString()
    ? `/${encodeURIComponent(topic)}/json?${qs}`
    : `/${encodeURIComponent(topic)}/json`
  const res = await fetch(path, { credentials: 'include' })
  if (!res.ok) {
    const bodyText = await res.text().catch(() => '')
    let detail: unknown = bodyText
    try {
      detail = bodyText ? JSON.parse(bodyText) : bodyText
    } catch {
      /* keep raw text */
    }
    throw new Error(
      `messages ${res.status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`,
    )
  }
  return res.json() as Promise<MessageOut[]>
}

export type SseTopicEvent =
  | { type: 'ready'; data: { topic: string } }
  | { type: 'message'; data: MessageOut }
  | { type: 'ping' }
  | { type: 'error'; error: Event | Error }

export interface SseTopicHandle {
  close: () => void
}

/**
 * Subscribe to topic SSE stream: `GET /{topic}/sse`.
 * Emits typed events; `ping` events are heartbeat (caller may use for liveness).
 */
export function subscribeTopic(topic: string, listener: (event: SseTopicEvent) => void): SseTopicHandle {
  const es = new EventSource(`/${encodeURIComponent(topic)}/sse`, { withCredentials: true })

  es.addEventListener('ready', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data) as { topic: string }
      listener({ type: 'ready', data })
    } catch (err) {
      listener({ type: 'error', error: err as Error })
    }
  })

  es.addEventListener('message', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent).data) as MessageOut
      listener({ type: 'message', data })
    } catch (err) {
      listener({ type: 'error', error: err as Error })
    }
  })

  es.addEventListener('ping', () => {
    listener({ type: 'ping' })
  })

  es.onerror = (e) => {
    listener({ type: 'error', error: e })
  }

  return { close: () => es.close() }
}