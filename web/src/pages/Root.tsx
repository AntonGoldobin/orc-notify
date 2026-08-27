import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'

export default function Root() {
  const { status } = useAuth()
  if (status === 'loading') return null
  return <Navigate to={status === 'authed' ? '/dashboard' : '/login'} replace />
}
