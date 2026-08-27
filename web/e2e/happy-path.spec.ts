import { test, expect } from '@playwright/test'
import { hmacSha256Hex, randomEmail, randomPassword } from './utils'

test('create agent → fire HMAC-signed webhook → see notification live', async ({ page, request }) => {
  const email = randomEmail()
  const password = randomPassword()

  // 1. Register
  await page.goto('/register')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: /create account/i }).click()
  await expect(page).toHaveURL('/dashboard')

  // 2. Create an agent
  await page.goto('/keys')
  await page.getByRole('button', { name: /new agent/i }).click()
  await page.getByLabel('Name').fill('e2e-agent')
  await page.getByRole('button', { name: /^create$/i }).click()

  // 3. Capture the secret modal — save the webhook secret
  await expect(page.getByRole('heading', { name: /save your webhook secret/i })).toBeVisible()
  const secretInput = page.locator('input[readonly]').first()
  const agentSecret = await secretInput.inputValue()
  const agentIdText = await page.locator('code').first().textContent()
  expect(agentSecret).toBeTruthy()
  expect(agentIdText).toBeTruthy()
  const agentId = (agentIdText ?? '').replace(/[()]/g, '')
  await page.getByRole('button', { name: /i have saved it/i }).click()

  // 4. Fire a webhook signed with that secret via the page's fetch context
  //    (so the cookie is included if needed).
  const threadId = `e2e-${Date.now()}`
  const body = JSON.stringify({
    event: 'thread.completed',
    thread_id: threadId,
    status: 'completed',
    summary: 'Playwright E2E happy path',
    project_name: 'e2e',
  })
  const sig = await hmacSha256Hex(agentSecret, body)

  // POST directly via Playwright request — backend serves /v1/events outside the dev proxy.
  const apiBase = process.env.E2E_API_BASE ?? 'http://localhost:8000'
  const fireResp = await request.post(`${apiBase}/v1/events`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Agent-Id': agentId,
      'X-Signature': `sha256=${sig}`,
    },
    data: body,
  })
  expect(fireResp.ok(), `webhook fire failed: ${fireResp.status()} ${await fireResp.text()}`).toBe(true)

  // 5. Open dashboard, wait for the notification to appear (live SSE)
  await page.goto('/dashboard')
  await expect(page.getByText('Playwright E2E happy path').first()).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText(threadId).first()).toBeVisible()
})

test('root path redirects to /dashboard for authed user', async ({ page }) => {
  const email = randomEmail()
  const password = randomPassword()

  await page.goto('/register')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: /create account/i }).click()
  await expect(page).toHaveURL('/dashboard')

  // Now visit /
  await page.goto('/')
  await expect(page).toHaveURL('/dashboard')
})
