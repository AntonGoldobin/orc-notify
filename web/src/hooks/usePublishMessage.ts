import { useMutation, useQueryClient } from '@tanstack/react-query'
import { publish } from '@/api/publish'
import type { PublishInput } from '@/api/publish'
import { messagesKeys } from './useMessages'

export function usePublishMessage(topic: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: PublishInput) => publish(topic, input),
    onSuccess: ({ message }) => {
      // Optimistically prepend to messages cache for instant feedback.
      const queryKeys = qc.getQueryCache().findAll({ queryKey: messagesKeys.list(topic) })
      for (const q of queryKeys) {
        qc.setQueryData(q.queryKey, (prev) => {
          if (!Array.isArray(prev)) return prev
          if (prev.some((m: { id: string }) => m.id === message.id)) return prev
          return [message, ...prev]
        })
      }
    },
  })
}