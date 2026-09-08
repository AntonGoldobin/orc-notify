/**
 * Legacy Dashboard shim.
 *
 * The HeroUI SPA exposed `/dashboard` as the main notifications feed.
 * Phase 3 redirects to `/topics` (the new home). For users with stale
 * bookmarks, this page renders an old-style notifications feed with a
 * banner pointing at the new location. Removed in Phase 4 cutover.
 */
import { Link } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { ArrowRight, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { history, subscribe, type SseEvent } from '@/api/events'
import type { HistoryOut } from '@/api/types'
import { formatRelative } from '@/lib/utils'

interface FeedItem extends HistoryOut {
  _source: 'history' | 'live'
}

export default function LegacyDashboard() {
  const [items, setItems] = useState<FeedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)

  const loadHistory = useCallback(async () => {
    const hist = await history({ limit: 50 })
    setItems(hist.map((h) => ({ ...h, _source: 'history' as const })))
  }, [])

  useEffect(() => {
    void loadHistory().finally(() => setLoading(false))
    const handle = subscribe((evt: SseEvent) => {
      if (evt.type === 'ready') setConnected(true)
      else if (evt.type === 'notification') {
        const n = evt.data
        const item: FeedItem = {
          notification_id: n.notification_id,
          event_id: n.event_id,
          rule_id: n.rule_id,
          delivered_at: n.delivered_at,
          event_name: n.event,
          thread_id: n.thread_id,
          project_name: n.project_name,
          summary: n.summary,
          status: n.status,
          pr_url: n.pr_url,
          occurred_at: n.occurred_at,
          rule_name: null,
          _source: 'live',
        }
        setItems((prev) => [item, ...prev].slice(0, 100))
      } else if (evt.type === 'error') {
        setConnected(false)
        void loadHistory()
      }
    })
    return () => handle.close()
  }, [loadHistory])

  return (
    <div className="mx-auto max-w-4xl flex flex-col gap-4">
      <Card className="border-amber-500/50 bg-amber-50/40 dark:bg-amber-950/20">
        <CardHeader className="flex flex-row items-start gap-3 space-y-0">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
          <div>
            <CardTitle className="text-amber-900 dark:text-amber-200">
              Legacy view — moving to topic-anchored UI
            </CardTitle>
            <CardDescription className="text-amber-800/80 dark:text-amber-300/80">
              The new home is <Link to="/topics" className="font-mono underline">/topics</Link> — one card per topic with its own messages, publish, and settings. This page will be removed in a future release.
            </CardDescription>
          </div>
          <Button asChild size="sm" className="ml-auto">
            <Link to="/topics">
              Go to Topics <ArrowRight className="h-4 w-4 ml-1" />
            </Link>
          </Button>
        </CardHeader>
      </Card>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Legacy notifications feed</h1>
        <Badge variant={connected ? 'default' : 'outline'} className="font-mono">
          {connected ? 'LIVE' : 'offline'}
        </Badge>
      </div>

      {loading ? (
        <Skeleton className="h-32 w-full" />
      ) : items.length === 0 ? (
        <Card className="p-8 text-center text-muted-foreground">
          No notifications yet.
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <Card key={`${item._source}-${item.notification_id}`} className="p-4">
              <div className="flex items-start justify-between gap-2 mb-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="font-mono">{item.event_name}</Badge>
                  {item.status && <Badge variant="secondary">{item.status}</Badge>}
                </div>
                <span className="text-xs text-muted-foreground">{formatRelative(item.delivered_at)}</span>
              </div>
              {item.summary && <p className="text-sm mt-1">{item.summary}</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}