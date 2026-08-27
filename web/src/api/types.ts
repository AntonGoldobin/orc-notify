/**
 * TypeScript shapes mirroring orc-notify backend Pydantic models.
 * Source: orc-notify/app/schemas.py + inline schemas in app/routers/*.py.
 * Keep in sync manually when backend changes.
 */

export interface UserOut {
  id: string
  email: string
  created_at: string
}

export interface RegisterIn {
  email: string
  password: string
}

export interface LoginIn {
  email: string
  password: string
}

export interface ResetRequestIn {
  email: string
}

export interface ResetConfirmIn {
  token: string
  new_password: string
}

export interface ChangePasswordIn {
  current_password: string
  new_password: string
}

export interface AgentOut {
  id: string
  agent_id: string
  name: string
  created_at: string
  last_event_at: string | null
}

export interface AgentCreateIn {
  name: string
  agent_id?: string
}

export interface AgentCreatedOut extends AgentOut {
  /** Returned ONCE on create/rotate. Never persisted client-side beyond a single view. */
  webhook_secret: string | null
}

export interface AgentHealthOut {
  agent_id: string
  last_event_at: string | null
  status: string
}

export interface RuleIn {
  name: string
  event_pattern: string
  channel?: string
  enabled?: boolean
}

export type RulePatch = Partial<RuleIn>

export interface RuleOut {
  id: string
  name: string
  event_pattern: string
  channel: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface HistoryOut {
  notification_id: number
  event_id: number
  rule_id: string | null
  delivered_at: string
  event_name: string
  thread_id: string | null
  project_name: string | null
  summary: string | null
  status: string | null
  pr_url: string | null
  occurred_at: string | null
  rule_name: string | null
}

/** SSE payload as actually emitted by the backend (field is `event`, not `event_name`). */
export interface SseNotification {
  notification_id: number
  event_id: number
  rule_id: string | null
  delivered_at: string
  event: string
  thread_id: string | null
  project_name: string | null
  summary: string | null
  status: string | null
  pr_url: string | null
  occurred_at: string | null
}

export interface SseReady {
  user_id: string
}
