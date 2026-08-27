import { api } from './client'
import type { AgentCreateIn, AgentCreatedOut, AgentHealthOut, AgentOut } from './types'

export function list() {
  return api<AgentOut[]>('/api/keys')
}

export function create(input: AgentCreateIn) {
  return api<AgentCreatedOut>('/api/keys', { method: 'POST', body: input })
}

export function remove(agentId: string) {
  return api<void>(`/api/keys/${encodeURIComponent(agentId)}`, { method: 'DELETE' })
}

export function rotate(agentId: string) {
  return api<AgentCreatedOut>(`/api/keys/${encodeURIComponent(agentId)}/rotate-secret`, { method: 'POST' })
}

export function health(agentId: string) {
  return api<AgentHealthOut>(`/v1/agents/${encodeURIComponent(agentId)}/health`)
}
