import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Input, Label, Typography } from '@heroui/react'
import { Topbar } from '../components/Topbar'
import { useAuth } from '../auth/AuthProvider'
import { changePassword } from '../api/auth'
import { ApiError } from '../api/client'

export default function Settings() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters')
      return
    }
    setSubmitting(true)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      setSuccess(true)
      setCurrentPassword('')
      setNewPassword('')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Current password is incorrect')
      } else if (err instanceof ApiError && err.status === 422) {
        setError('Invalid new password (min 8 chars)')
      } else {
        setError('Change failed — try again')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-svh flex flex-col">
      <Topbar />
      <main className="flex-1 p-4 max-w-2xl mx-auto w-full flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Settings</h1>

        <Card className="p-4">
          <Card.Header>
            <Card.Title>Account</Card.Title>
            <Card.Description>{user?.email}</Card.Description>
          </Card.Header>
          <Card.Content>
            <Typography className="text-sm text-default-500">
              Account created {user ? new Date(user.created_at).toLocaleString() : '—'}
            </Typography>
          </Card.Content>
        </Card>

        <Card className="p-4">
          <Card.Header>
            <Card.Title>Change password</Card.Title>
          </Card.Header>
          <Card.Content>
            <form onSubmit={onSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="current">Current password</Label>
                <Input
                  id="current"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  disabled={submitting}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="new">New password</Label>
                <Input
                  id="new"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  disabled={submitting}
                />
              </div>
              {error && <Typography className="text-sm text-danger">{error}</Typography>}
              {success && <Typography className="text-sm text-success">Password updated.</Typography>}
              <Button type="submit" variant="primary" isDisabled={submitting} className="self-start">
                {submitting ? 'Saving…' : 'Update password'}
              </Button>
            </form>
          </Card.Content>
        </Card>

        <Card className="p-4">
          <Card.Header>
            <Card.Title>Session</Card.Title>
          </Card.Header>
          <Card.Content>
            <Button variant="danger" onPress={handleLogout}>Log out</Button>
          </Card.Content>
        </Card>
      </main>
    </div>
  )
}
