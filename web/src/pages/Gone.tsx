import { Link } from 'react-router-dom'
import { ArrowRight, Archive } from 'lucide-react'
import { Button } from '@/components/ui/button'

/**
 * 410 Gone — for legacy SPA paths (`/dashboard`, `/rules`) that the old
 * Jinja2 UI used to serve. The shadcn UI uses topic-anchored URLs instead:
 * subscriptions live under `/topics/:name`, rule editing is per-topic.
 */
export default function Gone() {
  return (
    <div className="mx-auto max-w-xl flex flex-col items-center gap-4 p-8 text-center">
      <Archive className="h-12 w-12 text-muted-foreground" aria-hidden />
      <div>
        <h1 className="text-3xl font-semibold">410 — Gone</h1>
        <p className="mt-2 text-muted-foreground">
          This page was part of the old notifier UI. The new home is{' '}
          <Link to="/topics" className="font-mono underline">
            /topics
          </Link>{' '}
          — one card per topic with its own messages and settings.
        </p>
      </div>
      <Button asChild>
        <Link to="/topics">
          Go to Topics <ArrowRight className="h-4 w-4 ml-1" />
        </Link>
      </Button>
    </div>
  )
}
