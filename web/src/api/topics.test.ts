import { afterEach, describe, expect, it, vi } from 'vitest'
import { createTopic, deleteTopic, getTopic, listTopics, updateTopic } from './topics'

const originalFetch = globalThis.fetch

describe('topics API', () => {
  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  function jsonResponse(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    })
  }

  it('listTopics GETs /api/topics', async () => {
    const mock = vi.fn().mockResolvedValue(jsonResponse([]))
    globalThis.fetch = mock as unknown as typeof fetch
    await listTopics()
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/topics')
    expect(init.method).toBeUndefined()
    expect(init.credentials).toBe('include')
  })

  it('createTopic POSTs to /api/topics', async () => {
    const mock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: 't1', name: 'alerts', description: null,
        default_priority: 3, retention_days: 7, created_at: '2026-09-08', updated_at: '2026-09-08',
      }, 201),
    )
    globalThis.fetch = mock as unknown as typeof fetch
    const out = await createTopic({ name: 'alerts' })
    expect(out.name).toBe('alerts')
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/topics')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ name: 'alerts' })
  })

  it('updateTopic PATCHes /api/topics/{name}', async () => {
    const mock = vi.fn().mockResolvedValue(jsonResponse({
      id: 't1', name: 'alerts', description: 'updated',
      default_priority: 5, retention_days: 14, created_at: '2026-09-08', updated_at: '2026-09-09',
    }))
    globalThis.fetch = mock as unknown as typeof fetch
    await updateTopic('alerts', { description: 'updated', default_priority: 5 })
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/topics/alerts')
    expect(init.method).toBe('PATCH')
  })

  it('deleteTopic DELETEs /api/topics/{name}', async () => {
    const mock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    globalThis.fetch = mock as unknown as typeof fetch
    await deleteTopic('alerts')
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/topics/alerts')
    expect(init.method).toBe('DELETE')
  })

  it('getTopic URL-encodes the topic name', async () => {
    const mock = vi.fn().mockResolvedValue(jsonResponse({
      id: 't1', name: 'a.b', description: null,
      default_priority: 3, retention_days: 7, created_at: '2026-09-08', updated_at: '2026-09-08',
    }))
    globalThis.fetch = mock as unknown as typeof fetch
    await getTopic('a.b')
    const [url] = mock.mock.calls[0]
    expect(url).toBe('/api/topics/a.b')
  })
})