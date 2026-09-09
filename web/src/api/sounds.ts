import { api } from './client'
import type { SoundIn, SoundOut, SoundPatch } from './types'

export function listSounds(): Promise<SoundOut[]> {
  return api<SoundOut[]>('/api/sounds')
}

export function createSound(input: SoundIn): Promise<SoundOut> {
  return api<SoundOut>('/api/sounds', { method: 'POST', body: input })
}

export function updateSound(id: string, patch: SoundPatch): Promise<SoundOut> {
  return api<SoundOut>(`/api/sounds/${encodeURIComponent(id)}`, { method: 'PATCH', body: patch })
}

export function deleteSound(id: string): Promise<void> {
  return api<void>(`/api/sounds/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
