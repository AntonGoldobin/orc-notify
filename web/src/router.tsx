import { Navigate, Outlet, createBrowserRouter, type RouteObject } from 'react-router-dom'
import { useAuth } from './auth/AuthProvider'

import Login from './pages/Login'
import Register from './pages/Register'
import Reset from './pages/Reset'
import Dashboard from './pages/Dashboard'
import Keys from './pages/Keys'
import Rules from './pages/Rules'
import Settings from './pages/Settings'
import Root from './pages/Root'
import NotFound from './pages/NotFound'

function ProtectedRoute() {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'anon') return <Navigate to="/login" replace />
  return <Outlet />
}

function AnonOnly() {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'authed') return <Navigate to="/dashboard" replace />
  return <Outlet />
}

const routes: RouteObject[] = [
  { path: '/', element: <Root /> },
  {
    element: <AnonOnly />,
    children: [
      { path: '/login', element: <Login /> },
      { path: '/register', element: <Register /> },
      { path: '/reset', element: <Reset /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/dashboard', element: <Dashboard /> },
      { path: '/keys', element: <Keys /> },
      { path: '/rules', element: <Rules /> },
      { path: '/settings', element: <Settings /> },
    ],
  },
  { path: '*', element: <NotFound /> },
]

export const router = createBrowserRouter(routes)
