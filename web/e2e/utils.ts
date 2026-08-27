/**
 * HMAC-SHA256 helper for E2E webhook signing.
 * Mirrors app/security.py sign_event: hex(hmac_sha256(secret, raw_body_bytes))
 */
export async function hmacSha256Hex(secret: string, body: string): Promise<string> {
  const enc = new TextEncoder()
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(body))
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

export function randomEmail(): string {
  const ts = Date.now().toString(36)
  const rnd = Math.random().toString(36).slice(2, 8)
  return `e2e-${ts}-${rnd}@example.com`
}

export function randomPassword(): string {
  const ts = Date.now().toString(36)
  return `Pass!${ts}${Math.random().toString(36).slice(2, 8)}`
}
