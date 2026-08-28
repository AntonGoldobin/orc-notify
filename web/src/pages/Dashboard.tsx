import { useCallback, useEffect, useRef, useState } from 'react'
import { Card, Chip, Spinner, Typography } from '@heroui/react'
import { Topbar } from '../components/Topbar'
import { history, subscribe, type SseEvent, type SseHandle } from '../api/events'
import type { HistoryOut } from '../api/types'

interface FeedItem extends HistoryOut {
  _source: 'history' | 'live'
}

export default function Dashboard() {
  const [items, setItems] = useState<FeedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const handleRef = useRef<SseHandle | null>(null)

  const loadHistory = useCallback(async () => {
    const hist = await history({ limit: 50 })
    setItems(hist.map((h) => ({ ...h, _source: 'history' as const })))
  }, [])

  useEffect(() => {
    void loadHistory().finally(() => setLoading(false))

    const handle = subscribe((evt: SseEvent) => {
      if (evt.type === 'ready') {
        setConnected(true)
      } else if (evt.type === 'notification') {
        // Map SSE payload to a HistoryOut-like shape so the feed renders uniformly.
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
        // Backfill on reconnect
        void loadHistory()
      }
    })
    handleRef.current = handle
    return () => {
      handle.close()
    }
  }, [loadHistory])

  return (
    <div className="min-h-svh flex flex-col">
      <Topbar />
      <main className="flex-1 p-4 max-w-4xl mx-auto w-full">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-semibold">Notifications</h1>
          <div className="flex items-center gap-2 text-sm">
            <Chip size="sm" color={connected ? 'success' : 'default'} variant="soft">
              {connected ? 'Live' : 'Disconnected'}
            </Chip>
            <button
              type="button"
              onClick={() => void loadHistory()}
              className="text-primary hover:underline text-sm"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12 items-center gap-2 text-default-500">
            <Spinner /> Loading…
          </div>
        ) : items.length === 0 ? (
          <Card className="p-8 text-center text-default-500">
            No notifications yet. Create an agent, set a rule, and fire a webhook to see something here.
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            {items.map((item) => (
              <NotificationCard key={`${item._source}-${item.notification_id}`} item={item} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function NotificationCard({ item }: { item: FeedItem }) {
  const time = new Date(item.delivered_at).toLocaleString()
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Chip size="sm" variant="soft" color="accent">{item.event_name}</Chip>
          {item.status && (
            <Chip size="sm" variant="soft" color={item.status === 'completed' ? 'success' : 'default'}>
              {item.status}
            </Chip>
          )}
          {item.project_name && <Chip size="sm" variant="secondary">{item.project_name}</Chip>}
        </div>
        <Typography className="text-xs text-default-500 shrink-0">{time}</Typography>
      </div>
      {item.summary && <p className="text-sm mt-1">{item.summary}</p>}
      <div className="flex items-center gap-3 mt-2 text-xs text-default-500 flex-wrap">
        {item.thread_id && <span>thread: <code>{item.thread_id}</code></span>}
        {item.rule_name && <span>via {item.rule_name}</span>}
        {item.pr_url && (
          <a href={item.pr_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
            View PR →
          </a>
        )}
      </div>
    </Card>
  )
}
