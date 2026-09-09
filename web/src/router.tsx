import { Navigate, Outlet, createBrowserRouter, type RouteObject } from 'react-router-dom'
import { useAuth } from './auth/AuthProvider'

import { AppLayout } from './layouts/AppLayout'

import Login from './pages/Login'
import Register from './pages/Register'
import Reset from './pages/Reset'
import Topics from './pages/Topics'
import TopicDetail from './pages/TopicDetail'
import Keys from './pages/Keys'
import Settings from './pages/Settings'
import Root from './pages/Root'
import NotFound from './pages/NotFound'
import Gone from './pages/Gone'

function ProtectedRoute() {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'anon') return <Navigate to="/login" replace />
  return <Outlet />
}

function AnonOnly() {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'authed') return <Navigate to="/topics" replace />
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
      {
        element: <AppLayout />,
        children: [
          { path: '/topics', element: <Topics /> },
          { path: '/topics/:name', element: <TopicDetail /> },
          { path: '/topics/:name/:tab', element: <TopicDetail /> },
          { path: '/keys', element: <Keys /> },
          { path: '/settings', element: <Settings /> },
        ],
      },
    ],
  },
  // Legacy paths from the Jinja2 UI — return 410 Gone with a link to /topics.
  { path: '/dashboard', element: <Gone /> },
  { path: '/rules', element: <Gone /> },
  { path: '*', element: <NotFound /> },
]

export const router = createBrowserRouter(routes)