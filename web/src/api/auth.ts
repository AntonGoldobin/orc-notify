import { api } from './client'
import type { LoginIn, RegisterIn, ResetConfirmIn, ResetRequestIn, UserOut, ChangePasswordIn } from './types'

export function register(input: RegisterIn) {
  return api<UserOut>('/auth/register', { method: 'POST', body: input })
}

export function login(input: LoginIn) {
  return api<UserOut>('/auth/login', { method: 'POST', body: input })
}

export function logout() {
  return api<void>('/auth/logout', { method: 'POST' })
}

export function me() {
  return api<UserOut>('/auth/me')
}

export function requestReset(input: ResetRequestIn) {
  return api<void>('/auth/reset-password', { method: 'POST', body: input })
}

export function confirmReset(input: ResetConfirmIn) {
  return api<void>('/auth/reset-password/confirm', { method: 'POST', body: input })
}

export function changePassword(input: ChangePasswordIn) {
  return api<void>('/auth/change-password', { method: 'POST', body: input })
}
