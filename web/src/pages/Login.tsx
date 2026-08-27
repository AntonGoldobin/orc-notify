import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, Input, Label, Typography } from '@heroui/react'
import { login } from '../api/auth'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const { refresh } = useAuth()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login({ email, password })
      await refresh()
      navigate('/dashboard', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Invalid email or password')
      } else {
        setError('Login failed — try again')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-svh p-4">
      <Card className="w-full max-w-sm p-6">
        <Card.Header>
          <Card.Title>Sign in</Card.Title>
          <Card.Description>Welcome back to orc-notify</Card.Description>
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
                autoComplete="current-password"
                disabled={submitting}
              />
            </div>
            {error && <Typography className="text-sm text-danger">{error}</Typography>}
            <Button type="submit" variant="primary" isDisabled={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
            <div className="text-sm text-default-600 text-center">
              No account? <Link to="/register" className="text-primary hover:underline">Register</Link>
            </div>
          </form>
        </Card.Content>
      </Card>
    </div>
  )
}
