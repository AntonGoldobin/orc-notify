import { api } from './client'
import type { RuleIn, RuleOut, RulePatch } from './types'

export function list() {
  return api<RuleOut[]>('/api/rules')
}

export function create(input: RuleIn) {
  return api<RuleOut>('/api/rules', { method: 'POST', body: input })
}

export function update(id: string, patch: RulePatch) {
  return api<RuleOut>(`/api/rules/${encodeURIComponent(id)}`, { method: 'PUT', body: patch })
}

export function remove(id: string) {
  return api<void>(`/api/rules/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
