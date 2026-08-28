import { test, expect } from '@playwright/test'
import { randomEmail, randomPassword } from './utils'

test('register → logout → login round-trip', async ({ page }) => {
  const email = randomEmail()
  const password = randomPassword()

  // Register
  await page.goto('/register')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: /create account/i }).click()
  await expect(page).toHaveURL('/dashboard')
  await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()

  // Logout via Settings → Session → Log out
  await page.goto('/settings')
  await page.getByRole('button', { name: /log out/i }).click()
  await expect(page).toHaveURL('/login')

  // Login again with same creds
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page).toHaveURL('/dashboard')
})

test('logout returns to /login from any protected route', async ({ page }) => {
  await page.goto('/dashboard')
  // Should redirect to /login (anon)
  await expect(page).toHaveURL('/login')
})

test('protected route redirects anon user to /login', async ({ page }) => {
  await page.goto('/keys')
  await expect(page).toHaveURL('/login')
})
