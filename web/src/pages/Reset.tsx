import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { confirmReset, requestReset } from '@/api/auth'
import { ApiError } from '@/api/client'

export default function Reset() {
  const [search] = useSearchParams()
  const token = search.get('token') ?? ''
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const hasToken = token.length >= 16

  const onRequest = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setMessage(null)
    setSubmitting(true)
    try {
      await requestReset({ email })
      setMessage('If the email exists, a reset link has been generated. Check server logs.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) setError('Invalid email')
      else setError('Request failed — try again')
    } finally {
      setSubmitting(false)
    }
  }

  const onConfirm = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await confirmReset({ token, new_password: newPassword })
      navigate('/login', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setError('Invalid or expired token')
      else setError('Reset failed — try again')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-svh p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{hasToken ? 'Set new password' : 'Reset password'}</CardTitle>
          <CardDescription>
            {hasToken ? 'Choose a new password' : 'We will print a reset link to the server logs'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {hasToken ? (
            <form onSubmit={onConfirm} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="new-password">New password</Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  disabled={submitting}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Resetting…' : 'Reset password'}
              </Button>
            </form>
          ) : (
            <form onSubmit={onRequest} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={submitting}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              {message && <p className="text-sm text-emerald-600">{message}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Requesting…' : 'Send reset link'}
              </Button>
            </form>
          )}
          <div className="text-sm text-muted-foreground text-center mt-4">
            <Link to="/login" className="text-primary hover:underline">Back to sign in</Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}