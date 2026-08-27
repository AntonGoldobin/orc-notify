import { afterEach, describe, expect, it, vi } from 'vitest'
import * as auth from './auth'

const originalFetch = globalThis.fetch

describe('auth API wrappers', () => {
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

  it('login posts email+password to /auth/login', async () => {
    const mock = vi.fn().mockResolvedValue(jsonResponse({ id: 'u1', email: 'a@b.c', created_at: '2026-01-01' }))
    globalThis.fetch = mock as unknown as typeof fetch
    const u = await auth.login({ email: 'a@b.c', password: '12345678' })
    expect(u.email).toBe('a@b.c')
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/auth/login')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ email: 'a@b.c', password: '12345678' })
  })

  it('me throws on 401 (no cookie)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ detail: 'no' }, 401)) as unknown as typeof fetch
    await expect(auth.me()).rejects.toMatchObject({ status: 401 })
  })

  it('register returns user and sets cookie (set by browser, not testable here)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ id: 'u1', email: 'a@b.c', created_at: '2026' })) as unknown as typeof fetch
    const u = await auth.register({ email: 'a@b.c', password: 'longenough' })
    expect(u.email).toBe('a@b.c')
  })

  it('changePassword posts current + new', async () => {
    const mock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    globalThis.fetch = mock as unknown as typeof fetch
    await auth.changePassword({ current_password: 'oldpasss', new_password: 'newpasss' })
    const [url, init] = mock.mock.calls[0]
    expect(url).toBe('/auth/change-password')
    expect(JSON.parse(init.body as string)).toEqual({ current_password: 'oldpasss', new_password: 'newpasss' })
  })
})
