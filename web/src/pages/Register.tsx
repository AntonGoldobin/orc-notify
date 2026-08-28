import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, Input, Label, Typography } from '@heroui/react'
import { register } from '../api/auth'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

export default function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const { refresh } = useAuth()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setSubmitting(true)
    try {
      await register({ email, password })
      await refresh()
      navigate('/dashboard', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('Email is already registered')
      } else if (err instanceof ApiError && err.status === 422) {
        setError('Invalid email or password (min 8 chars)')
      } else {
        setError('Registration failed — try again')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-svh p-4">
      <Card className="w-full max-w-sm p-6">
        <Card.Header>
          <Card.Title>Create account</Card.Title>
          <Card.Description>Get an orc-notify account</Card.Description>
        </Card.Header>
        <Card.Content>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                disabled={submitting}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                disabled={submitting}
              />
            </div>
            {error && <Typography className="text-sm text-danger">{error}</Typography>}
            <Button type="submit" variant="primary" isDisabled={submitting}>
              {submitting ? 'Creating…' : 'Create account'}
            </Button>
            <div className="text-sm text-default-600 text-center">
              Already registered? <Link to="/login" className="text-primary hover:underline">Sign in</Link>
            </div>
          </form>
        </Card.Content>
      </Card>
    </div>
  )
}
