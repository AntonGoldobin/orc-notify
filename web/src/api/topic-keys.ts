import { api } from './client'
import type { TopicKeyCreatedOut, TopicKeyIn, TopicKeyOut, TopicKeyPatch } from './types'

export function listKeys(topic: string): Promise<TopicKeyOut[]> {
  return api<TopicKeyOut[]>(`/api/topics/${encodeURIComponent(topic)}/keys`)
}

export function createKey(topic: string, input: TopicKeyIn): Promise<TopicKeyCreatedOut> {
  return api<TopicKeyCreatedOut>(`/api/topics/${encodeURIComponent(topic)}/keys`, {
    method: 'POST',
    body: input,
  })
}

/**
 * PATCH always rotates the secret (see app/routers/topic_keys.py).
 * Returns fresh secret — caller must store it.
 */
export function patchKey(topic: string, keyId: string, patch: TopicKeyPatch): Promise<TopicKeyCreatedOut> {
  return api<TopicKeyCreatedOut>(
    `/api/topics/${encodeURIComponent(topic)}/keys/${encodeURIComponent(keyId)}`,
    { method: 'PATCH', body: patch },
  )
}

export function deleteKey(topic: string, keyId: string): Promise<void> {
  return api<void>(`/api/topics/${encodeURIComponent(topic)}/keys/${encodeURIComponent(keyId)}`, {
    method: 'DELETE',
  })
}