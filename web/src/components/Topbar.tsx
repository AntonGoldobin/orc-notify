import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@heroui/react'
import { useAuth } from '../auth/AuthProvider'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/keys', label: 'Keys' },
  { to: '/rules', label: 'Rules' },
  { to: '/settings', label: 'Settings' },
] as const

export function Topbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="flex items-center justify-between gap-4 px-4 py-3 border-b border-default-200">
      <div className="flex items-center gap-6">
        <Link to="/dashboard" className="font-semibold text-lg">orc-notify</Link>
        <nav className="flex items-center gap-1">
          {NAV.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              className={
                'px-3 py-1.5 rounded-md text-sm ' +
                (pathname === n.to
                  ? 'bg-default-100 text-foreground font-medium'
                  : 'text-default-600 hover:bg-default-50')
              }
            >
              {n.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <ThemeToggle />
        {user && <span className="text-sm text-default-600 hidden sm:inline">{user.email}</span>}
        <Button size="sm" variant="secondary" onPress={handleLogout}>Log out</Button>
      </div>
    </header>
  )
}
