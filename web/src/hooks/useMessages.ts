import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listMessages } from '@/api/messages'
import type { MessageOut } from '@/api/types'

export const messagesKeys = {
  all: ['messages'] as const,
  list: (topic: string) => [...messagesKeys.all, topic] as const,
}

/**
 * Fetch latest messages for a topic (since=0, latest 200 by default).
 * Use `useLiveMessages` to overlay SSE updates on top of this query.
 */
export function useMessages(topic: string, opts?: { limit?: number }) {
  return useQuery({
    queryKey: [...messagesKeys.list(topic), opts?.limit ?? 200] as const,
    queryFn: () => listMessages(topic, { limit: opts?.limit ?? 200 }),
    enabled: !!topic,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  })
}

/**
 * Merge a freshly-arrived live message into the topic's query cache, deduped by id.
 * Caller passes the result of `subscribeTopic` — we close the handle on unmount.
 *
 * Returns a STABLE reference via useCallback. Without memoisation, this hook
 * would create a fresh closure on every render, causing the consumer's
 * useEffect(..., [topic, onLive]) to tear down + reconnect the EventSource
 * each render — messages arriving during the reconnect window would be lost.
 */
export function useLiveMessages(topic: string) {
  const qc = useQueryClient()
  return useCallback(
    (msg: MessageOut) => {
      const queryKeys = qc.getQueryCache().findAll({ queryKey: messagesKeys.list(topic) })
      for (const q of queryKeys) {
        qc.setQueryData<MessageOut[]>(q.queryKey, (prev) => {
          if (!prev) return [msg]
          if (prev.some((m) => m.id === msg.id)) return prev
          return [msg, ...prev]
        })
      }
    },
    [qc, topic],
  )
}