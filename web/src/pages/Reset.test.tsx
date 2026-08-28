import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Reset from './Reset'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'

function renderReset(url = '/reset') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/reset" element={<Reset />} />
        <Route path="/login" element={<div data-testid="at-login">LOGIN</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<Reset>', () => {
  it('shows request form when no token in URL', () => {
    renderReset('/reset')
    expect(screen.getByText(/reset password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument()
  })

  it('shows confirm form when ?token=... is present', () => {
    renderReset('/reset?token=fake-token-at-least-sixteen-chars')
    expect(screen.getByText(/set new password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reset password/i })).toBeInTheDocument()
  })

  it('submits confirm and navigates to /login on success', async () => {
    const confirmSpy = vi.spyOn(authApi, 'confirmReset').mockResolvedValue(undefined)
    renderReset('/reset?token=fake-token-at-least-sixteen-chars')
    await userEvent.type(screen.getByLabelText(/new password/i), 'newpassword')
    await userEvent.click(screen.getByRole('button', { name: /reset password/i }))
    await waitFor(() => expect(screen.getByTestId('at-login')).toBeInTheDocument())
    expect(confirmSpy).toHaveBeenCalledWith({
      token: 'fake-token-at-least-sixteen-chars',
      new_password: 'newpassword',
    })
  })

  it('shows error on 400', async () => {
    vi.spyOn(authApi, 'confirmReset').mockRejectedValue(
      new ApiError(400, { detail: 'Invalid or expired' }),
    )
    renderReset('/reset?token=fake-token-at-least-sixteen-chars')
    await userEvent.type(screen.getByLabelText(/new password/i), 'newpassword')
    await userEvent.click(screen.getByRole('button', { name: /reset password/i }))
    await waitFor(() => expect(screen.getByText(/invalid or expired/i)).toBeInTheDocument(), { timeout: 3000 })
  })
})
