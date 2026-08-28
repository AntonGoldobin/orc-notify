import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Login from './Login'
import { AuthProvider } from '../auth/AuthProvider'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<div data-testid="at-dashboard">DASH</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('<Login>', () => {
  it('submits credentials and navigates to /dashboard on success', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValue(new Error('401')) // initial me() call → anon
    const loginSpy = vi.spyOn(authApi, 'login').mockResolvedValue({
      id: 'u1', email: 'a@b.c', created_at: '2026-01-01',
    })
    vi.spyOn(authApi, 'me').mockResolvedValueOnce({ id: 'u1', email: 'a@b.c', created_at: '2026-01-01' })

    renderLogin()
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.c')
    await userEvent.type(screen.getByLabelText(/password/i), 'verysecret')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(screen.getByTestId('at-dashboard')).toBeInTheDocument())
    expect(loginSpy).toHaveBeenCalledWith({ email: 'a@b.c', password: 'verysecret' })
  })

  it('shows error message on 401', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValue(new Error('401'))
    vi.spyOn(authApi, 'login').mockRejectedValue(
      new ApiError(401, { detail: 'Invalid' }),
    )
    renderLogin()
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.c')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrongpassword')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument(), { timeout: 3000 })
  })
})
