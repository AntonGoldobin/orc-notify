import { afterEach, describe, expect, it, vi } from 'vitest'
import { listMessages, subscribeTopic, type SseTopicHandle } from './messages'

const originalFetch = globalThis.fetch

type GlobalWithES = typeof globalThis & { EventSource: new (url: string, init?: { withCredentials?: boolean }) => unknown }

describe('messages API', () => {
  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('listMessages GETs /{topic}/json with no params by default', async () => {
    const mock = vi.fn().mockResolvedValue(new Response('[]', {
      status: 200, headers: { 'content-type': 'application/x-ndjson' },
    }))
    globalThis.fetch = mock as unknown as typeof fetch
    const res = await listMessages('alerts')
    expect(res).toEqual([])
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/alerts/json')
    expect(init.credentials).toBe('include')
  })

  it('listMessages appends ?since=&limit= when given', async () => {
    const mock = vi.fn().mockResolvedValue(new Response('[]', {
      status: 200, headers: { 'content-type': 'application/x-ndjson' },
    }))
    globalThis.fetch = mock as unknown as typeof fetch
    await listMessages('alerts', { since: 1700000000, limit: 50 })
    const [url] = mock.mock.calls[0]
    expect(url).toBe('/alerts/json?since=1700000000&limit=50')
  })

  it('listMessages URL-encodes topic name with dots', async () => {
    const mock = vi.fn().mockResolvedValue(new Response('[]', {
      status: 200, headers: { 'content-type': 'application/x-ndjson' },
    }))
    globalThis.fetch = mock as unknown as typeof fetch
    await listMessages('my.topic')
    const [url] = mock.mock.calls[0]
    // encodeURIComponent preserves '.' so this stays readable
    expect(url).toBe('/my.topic/json')
  })

  it('listMessages throws with status and detail on 404', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'unknown topic' }), {
        status: 404, headers: { 'content-type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    await expect(listMessages('nope')).rejects.toThrow(/messages 404/)
  })
})

describe('subscribeTopic()', () => {
  afterEach(() => {
    ;(globalThis as GlobalWithES).EventSource = (globalThis as GlobalWithES).EventSource
  })

  it('emits typed ready + message + ping events', () => {
    const sources: unknown[] = []
    const RealEventSource = (globalThis as GlobalWithES).EventSource
    function spy(this: unknown) {
      const es = new (RealEventSource as new (url: string) => unknown)('')
      sources.push(es)
      return es
    }
    ;(globalThis as unknown as GlobalWithES).EventSource = spy as unknown as GlobalWithES['EventSource']

    const received: unknown[] = []
    let handle: SseTopicHandle | undefined
    try {
      handle = subscribeTopic('alerts', (e) => received.push(e))
      const src = sources[0] as { __emit: (type: string, data?: unknown) => void }
      src.__emit('ready', { topic: 'alerts' })
      src.__emit('message', {
        id: 'm1', time: 1700000000, event: 'message', topic: 'alerts',
        title: null, message: 'hello', priority: 3, tags: [], click: null,
        icon: null, actions: null, content_type: 'text/plain',
      })
      src.__emit('ping')
    } finally {
      ;(globalThis as unknown as GlobalWithES).EventSource = RealEventSource
      handle?.close()
    }
    expect(received).toHaveLength(3)
    expect((received[0] as { type: string }).type).toBe('ready')
    expect((received[1] as { type: string; data: { message: string } }).data.message).toBe('hello')
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
    let handle: SseTopicHandle | undefined
    try {
      handle = subscribeTopic('alerts', (e) => received.push(e))
      const src = sources[0] as { __emit: (type: string, data?: unknown) => void }
      src.__emit('message', '{not valid json')
    } finally {
      ;(globalThis as unknown as GlobalWithES).EventSource = RealEventSource
      handle?.close()
    }
    expect(received[0]).toMatchObject({ type: 'error' })
  })
})