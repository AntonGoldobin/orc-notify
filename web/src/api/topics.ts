import { api } from './client'
import type { TopicIn, TopicOut, TopicPatch } from './types'

export function listTopics(): Promise<TopicOut[]> {
  return api<TopicOut[]>('/api/topics')
}

export function getTopic(name: string): Promise<TopicOut> {
  return api<TopicOut>(`/api/topics/${encodeURIComponent(name)}`)
}

export function createTopic(input: TopicIn): Promise<TopicOut> {
  return api<TopicOut>('/api/topics', { method: 'POST', body: input })
}

export function updateTopic(name: string, patch: TopicPatch): Promise<TopicOut> {
  return api<TopicOut>(`/api/topics/${encodeURIComponent(name)}`, { method: 'PATCH', body: patch })
}

export function deleteTopic(name: string): Promise<void> {
  return api<void>(`/api/topics/${encodeURIComponent(name)}`, { method: 'DELETE' })
}