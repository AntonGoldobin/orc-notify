import { afterEach, describe, expect, it, vi } from 'vitest'
import { createSound, deleteSound, listSounds, updateSound } from './sounds'

const originalFetch = globalThis.fetch

describe('sounds API', () => {
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

  it('listSounds GETs /api/sounds', async () => {
    const mock = vi.fn().mockResolvedValue(jsonResponse([]))
    globalThis.fetch = mock as unknown as typeof fetch
    await listSounds()
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/sounds')
    expect(init.method).toBeUndefined()
    expect(init.credentials).toBe('include')
  })

  it('createSound POSTs to /api/sounds', async () => {
    const mock = vi.fn().mockResolvedValue(
      jsonResponse({ id: 's1', name: 'ping', url: '/sounds/chime.wav', created_at: '2026-09-09' }, 201),
    )
    globalThis.fetch = mock as unknown as typeof fetch
    const out = await createSound({ name: 'ping', url: '/sounds/chime.wav' })
    expect(out.name).toBe('ping')
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/sounds')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ name: 'ping', url: '/sounds/chime.wav' })
  })

  it('updateSound PATCHes /api/sounds/{id}', async () => {
    const mock = vi.fn().mockResolvedValue(jsonResponse({
      id: 's1', name: 'ping2', url: '/sounds/bell.wav', created_at: '2026-09-09',
    }))
    globalThis.fetch = mock as unknown as typeof fetch
    await updateSound('s1', { name: 'ping2' })
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/sounds/s1')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ name: 'ping2' })
  })

  it('deleteSound DELETEs /api/sounds/{id}', async () => {
    const mock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    globalThis.fetch = mock as unknown as typeof fetch
    await deleteSound('s1')
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/api/sounds/s1')
    expect(init.method).toBe('DELETE')
  })

  it('URL-encodes ids with special characters', async () => {
    const mock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    globalThis.fetch = mock as unknown as typeof fetch
    await deleteSound('a/b')
    const [url] = mock.mock.calls[0]
    expect(url).toBe('/api/sounds/a%2Fb')
  })
})
