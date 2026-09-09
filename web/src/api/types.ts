/**
 * TypeScript shapes mirroring orc-notify backend Pydantic models.
 * Source: orc-notify/app/schemas.py + inline schemas in app/routers/*.py.
 * Keep in sync manually when backend changes.
 *
 * Topic / TopicKey / Message types are Phase 1 additions.
 */

// ── Users ──────────────────────────────────────────────────────────────────

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

// ── Sounds (per-topic notification sounds) ────────────────────────────────

export interface SoundOut {
  id: string
  name: string
  url: string
  created_at: string
}

export interface SoundIn {
  name: string
  url: string
}

export interface SoundPatch {
  name?: string | null
  url?: string | null
}

// ── Topics (Phase 1) ──────────────────────────────────────────────────────

export interface TopicIn {
  name: string
  description?: string | null
  default_priority?: number | null
  retention_days?: number | null
  sound_id?: string | null
}

export interface TopicPatch {
  description?: string | null
  default_priority?: number | null
  retention_days?: number | null
  sound_id?: string | null
}

export interface TopicOut {
  id: string
  name: string
  description: string | null
  default_priority: number
  retention_days: number
  created_at: string
  updated_at: string
  sound: SoundOut | null
}

// ── Topic keys (Phase 1) ──────────────────────────────────────────────────

export interface TopicKeyIn {
  name: string
  scopes?: string
}

export interface TopicKeyPatch {
  name?: string | null
  scopes?: string | null
}

export interface TopicKeyOut {
  id: string
  topic_id: string
  name: string
  scopes: string
  created_at: string
  last_used_at: string | null
}

/** Returned exactly once on create / patch-with-rotation — secret is plaintext. */
export interface TopicKeyCreatedOut extends TopicKeyOut {
  secret: string | null
}

// ── Messages (Phase 1) ────────────────────────────────────────────────────

/** ntfy.sh-compatible envelope served by `GET /{topic}/json`. */
export interface MessageOut {
  id: string
  time: number
  event: string
  topic: string
  title: string | null
  message: string
  priority: number
  tags: string[]
  click: string | null
  icon: string | null
  actions: Array<Record<string, unknown>> | null
  content_type: string
}

// ── Legacy: Rules / Agents / Events (kept until Phase 5) ──────────────────

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
  webhook_secret: string | null
}

export interface AgentHealthOut {
  agent_id: string
  last_event_at: string | null
  status: string
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
  topic_id: string | null
  topic_name: string | null
}

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
  topic_id: string | null
  topic_name: string | null
}

export interface SseReady {
  user_id: string
}