import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-svh gap-4 p-8">
      <h1 className="text-4xl font-semibold">404</h1>
      <p className="text-muted-foreground">Page not found</p>
      <Button asChild>
        <Link to="/topics">Back to topics</Link>
      </Button>
    </div>
  )
}