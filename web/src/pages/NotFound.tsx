import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-svh gap-4 p-8">
      <h1 className="text-4xl font-semibold">404</h1>
      <p className="text-default-600">Page not found</p>
      <Link to="/dashboard" className="text-sm text-primary hover:underline">
        Back to dashboard
      </Link>
    </div>
  )
}
