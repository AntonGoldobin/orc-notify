import type { MessageOut } from './types'

/**
 * Publish to a topic via ntfy.sh-compatible `POST /{topic}`.
 * Headers map: priority, title, tags (CSV), click, icon.
 * Body is raw text (or JSON; content-type decides serialization).
 */
export interface PublishInput {
  title?: string
  body: string
  priority?: number
  tags?: string[]
  click?: string
  icon?: string
  content_type?: string
}

export interface PublishResult {
  message: MessageOut
  created: boolean
}

export async function publish(topic: string, input: PublishInput): Promise<PublishResult> {
  const headers: Record<string, string> = {}
  const contentType = input.content_type ?? (typeof input.body === 'string' ? 'text/plain' : 'application/json')
  headers['Content-Type'] = contentType
  if (input.title !== undefined) headers['Title'] = input.title
  if (input.priority !== undefined) headers['Priority'] = String(input.priority)
  if (input.tags && input.tags.length > 0) headers['Tags'] = input.tags.join(',')
  if (input.click) headers['Click'] = input.click
  if (input.icon) headers['Icon'] = input.icon

  const res = await fetch(`/${encodeURIComponent(topic)}`, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: input.body,
  })
  if (!res.ok) {
    const bodyText = await res.text().catch(() => '')
    let detail: unknown = bodyText
    try {
      detail = bodyText ? JSON.parse(bodyText) : bodyText
    } catch {
      /* keep raw */
    }
    throw new Error(
      `publish ${res.status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`,
    )
  }
  const data = (await res.json()) as MessageOut
  return { message: data, created: res.status === 201 }
}