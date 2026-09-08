import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as keysApi from '@/api/topic-keys'
import type { TopicKeyIn, TopicKeyPatch } from '@/api/types'

export const topicKeysKeys = {
  all: ['topic-keys'] as const,
  list: (topic: string) => [...topicKeysKeys.all, topic] as const,
}

export function useTopicKeys(topic: string) {
  return useQuery({
    queryKey: topicKeysKeys.list(topic),
    queryFn: () => keysApi.listKeys(topic),
    enabled: !!topic,
  })
}

export function useCreateTopicKey(topic: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: TopicKeyIn) => keysApi.createKey(topic, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: topicKeysKeys.list(topic) }),
  })
}

export function usePatchTopicKey(topic: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ keyId, patch }: { keyId: string; patch: TopicKeyPatch }) =>
      keysApi.patchKey(topic, keyId, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: topicKeysKeys.list(topic) }),
  })
}

export function useDeleteTopicKey(topic: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => keysApi.deleteKey(topic, keyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: topicKeysKeys.list(topic) }),
  })
}