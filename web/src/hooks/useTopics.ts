import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as topicsApi from '@/api/topics'
import type { TopicIn, TopicOut, TopicPatch } from '@/api/types'

export const topicsKeys = {
  all: ['topics'] as const,
  list: () => [...topicsKeys.all, 'list'] as const,
  detail: (name: string) => [...topicsKeys.all, 'detail', name] as const,
}

export function useTopics() {
  return useQuery({ queryKey: topicsKeys.list(), queryFn: topicsApi.listTopics })
}

export function useTopic(name: string) {
  return useQuery({
    queryKey: topicsKeys.detail(name),
    queryFn: () => topicsApi.getTopic(name),
    enabled: !!name,
  })
}

export function useCreateTopic() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: TopicIn) => topicsApi.createTopic(input),
    onSuccess: (created) => {
      qc.setQueryData<TopicOut[]>(topicsKeys.list(), (prev) =>
        prev ? [created, ...prev] : [created],
      )
      qc.setQueryData(topicsKeys.detail(created.name), created)
    },
  })
}

export function useUpdateTopic(name: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: TopicPatch) => topicsApi.updateTopic(name, patch),
    onSuccess: (updated) => {
      qc.setQueryData(topicsKeys.detail(name), updated)
      qc.invalidateQueries({ queryKey: topicsKeys.list() })
    },
  })
}

export function useDeleteTopic() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => topicsApi.deleteTopic(name),
    onSuccess: (_void, name) => {
      qc.removeQueries({ queryKey: topicsKeys.detail(name) })
      qc.invalidateQueries({ queryKey: topicsKeys.list() })
      qc.removeQueries({ queryKey: ['messages', name] })
      qc.removeQueries({ queryKey: ['topic-keys', name] })
    },
  })
}