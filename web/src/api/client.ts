/**
 * Thin fetch wrapper. Same-origin (Vite proxy in dev, reverse proxy in prod).
 * All cookies are HttpOnly → never touch them in JS; just send credentials.
 */

export class ApiError extends Error {
  status: number
  detail: string | unknown

  constructor(status: number, detail: string | unknown) {
    super(`API ${status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export interface ApiInit extends Omit<RequestInit, 'body'> {
  body?: unknown
}

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { body, headers, ...rest } = init
  const isJson = body !== undefined && body !== null && !(body instanceof FormData) && !(body instanceof Blob) && !(body instanceof ArrayBuffer)
  const res = await fetch(path, {
    credentials: 'include',
    ...rest,
    headers: {
      ...(isJson ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    body: isJson && body !== undefined && body !== null ? JSON.stringify(body) : (body as BodyInit | null | undefined),
  })
  if (!res.ok) {
    let detail: string | unknown
    try {
      detail = await res.json()
    } catch {
      detail = res.statusText
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return (await res.json()) as T
}
