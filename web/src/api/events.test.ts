import { afterEach, describe, expect, it, vi } from 'vitest'
import { history, subscribe, type SseHandle } from './events'

const originalFetch = globalThis.fetch

type GlobalWithES = typeof globalThis & { EventSource: new (url: string, init?: { withCredentials?: boolean }) => unknown }

describe('events.history()', () => {
  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('GETs /api/events with no params by default', async () => {
    const mock = vi.fn().mockResolvedValue(new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }))
    globalThis.fetch = mock as unknown as typeof fetch
    const res = await history()
    expect(res).toEqual([])
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/events')
    expect(init.credentials).toBe('include')
  })

  it('appends ?limit=50&since=... when given', async () => {
    const mock = vi.fn().mockResolvedValue(new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }))
    globalThis.fetch = mock as unknown as typeof fetch
    await history({ limit: 50, since: '2026-08-27T00:00:00Z' })
    const [url] = mock.mock.calls[0]
    // Note: insertion order in URLSearchParams is `since` then `limit`.
    expect(url).toBe('/api/events?since=2026-08-27T00%3A00%3A00Z&limit=50')
  })

  it('throws on non-ok with parsed detail', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'no' }), { status: 401, headers: { 'content-type': 'application/json' } })) as unknown as typeof fetch
    await expect(history()).rejects.toThrow(/history 401/)
  })
})

describe('events.subscribe()', () => {
  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('emits typed notification events from EventSource', () => {
    // Capture the EventSource instance the test creates.
    const sources: unknown[] = []
    const RealEventSource = (globalThis as GlobalWithES).EventSource
    function spy(this: unknown) {
      const es = new (RealEventSource as new (url: string) => unknown)('')
      sources.push(es)
      return es
    }
    ;(globalThis as unknown as GlobalWithES).EventSource = spy as unknown as GlobalWithES['EventSource']

    const received: unknown[] = []
    let handle: SseHandle | undefined
    try {
      handle = subscribe((e) => received.push(e))
      const src = sources[0] as { __emit: (type: string, data?: unknown) => void }
      src.__emit('ready', { user_id: 'u1' })
      src.__emit('notification', { notification_id: 1, event_id: 2, rule_id: 'r1', delivered_at: '2026-08-27T00:00:00Z', event: 'thread.completed', thread_id: null, project_name: null, summary: null, status: 'completed', pr_url: null, occurred_at: null })
      src.__emit('ping')
    } finally {
      ;(globalThis as unknown as GlobalWithES).EventSource = RealEventSource
      handle?.close()
    }

    expect(received).toHaveLength(3)
    expect((received[0] as { type: string }).type).toBe('ready')
    expect((received[1] as { type: string; data: { event: string } }).data.event).toBe('thread.completed')
    expect((received[2] as { type: string }).type).toBe('ping')
  })

  it('emits error event on JSON parse failure', () => {
    const sources: unknown[] = []
    const RealEventSource = (globalThis as GlobalWithES).EventSource
    function spy(this: unknown) {
      const es = new (RealEventSource as new (url: string) => unknown)('')
      sources.push(es)
      return es
    }
    ;(globalThis as unknown as GlobalWithES).EventSource = spy as unknown as GlobalWithES['EventSource']

    const received: unknown[] = []
    let handle: SseHandle | undefined
    try {
      handle = subscribe((e) => received.push(e))
      const src = sources[0] as { __emit: (type: string, data?: unknown) => void }
      src.__emit('ready', 'not-json{{{')
    } finally {
      ;(globalThis as unknown as GlobalWithES).EventSource = RealEventSource
      handle?.close()
    }
    expect(received[0]).toMatchObject({ type: 'error' })
  })

  it('handle.close() is idempotent', () => {
    const sources: unknown[] = []
    const RealEventSource = (globalThis as GlobalWithES).EventSource
    function spy(this: unknown) {
      const es = new (RealEventSource as new (url: string) => unknown)('')
      sources.push(es)
      return es
    }
    ;(globalThis as unknown as GlobalWithES).EventSource = spy as unknown as GlobalWithES['EventSource']

    let handle: SseHandle | undefined
    try {
      handle = subscribe(() => {})
    } finally {
      ;(globalThis as unknown as GlobalWithES).EventSource = RealEventSource
    }
    expect(() => {
      handle?.close()
      handle?.close()
    }).not.toThrow()
    expect(sources).toHaveLength(1)
  })
})
