import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './client'

const originalFetch = globalThis.fetch

describe('api()', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('sends credentials: include and JSON content-type for object body', async () => {
    const mock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }),
    )
    globalThis.fetch = mock as unknown as typeof fetch

    const res = await api<{ ok: boolean }>('/x', { method: 'POST', body: { a: 1 } })
    expect(res).toEqual({ ok: true })

    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/x')
    expect(init.credentials).toBe('include')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(init.body).toBe(JSON.stringify({ a: 1 }))
  })

  it('returns undefined on 204 No Content', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch
    const res = await api<void>('/x')
    expect(res).toBeUndefined()
  })

  it('throws ApiError on 4xx with parsed JSON detail', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'oops' }), {
        status: 400,
        headers: { 'content-type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    let caught: unknown
    try {
      await api('/x')
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(ApiError)
    expect((caught as ApiError).status).toBe(400)
    expect((caught as ApiError).detail).toEqual({ detail: 'oops' })
  })

  it('falls back to plain text body when not JSON', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response('Bad Gateway plain text', { status: 502 }),
    ) as unknown as typeof fetch
    let caught: unknown
    try {
      await api('/x')
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(ApiError)
    expect((caught as ApiError).status).toBe(502)
    // detail should be the body text (since it's not JSON)
    expect((caught as ApiError).detail).toContain('Bad Gateway')
  })

  it('passes through non-object body without setting content-type', async () => {
    const mock = vi.fn().mockResolvedValue(new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } }))
    globalThis.fetch = mock as unknown as typeof fetch
    const fd = new FormData()
    fd.append('a', '1')
    await api('/x', { method: 'POST', body: fd })
    const init = mock.mock.calls[0][1] as RequestInit & { headers?: Record<string, string> }
    expect(init.headers?.['Content-Type']).toBeUndefined()
    expect(init.body).toBe(fd)
  })
})
