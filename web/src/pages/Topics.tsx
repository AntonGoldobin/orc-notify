import * as React from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Trash2, MoreHorizontal, Plus, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { useCreateTopic, useDeleteTopic, useTopics } from '@/hooks/useTopics'
import { formatRelative } from '@/lib/utils'
import { toast } from 'sonner'

export default function TopicsPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useTopics()
  const [searchParams, setSearchParams] = useSearchParams()
  const openNew = searchParams.get('new') === '1'
  const closeNew = React.useCallback(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('new')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  return (
    <div className="mx-auto max-w-6xl flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Topics</h1>
          <p className="text-sm text-muted-foreground">
            Publish-and-subscribe channels. Each topic is a private stream for your account.
          </p>
        </div>
        <Button onClick={() => setSearchParams({ new: '1' }, { replace: true })}>
          <Plus className="h-4 w-4 mr-1" /> New topic
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : !data || data.length === 0 ? (
        <Card className="p-8 text-center text-muted-foreground">
          No topics yet. Click <span className="font-medium">New topic</span> to create your first one.
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.map((t) => (
            <TopicCard key={t.id} topic={t} onOpen={() => navigate(`/topics/${encodeURIComponent(t.name)}`)} />
          ))}
        </div>
      )}

      <NewTopicDialog open={openNew} onClose={closeNew} />
    </div>
  )
}

function TopicCard({
  topic,
  onOpen,
}: {
  topic: { id: string; name: string; description: string | null; default_priority: number; retention_days: number; updated_at: string }
  onOpen: () => void
}) {
  const deleteMut = useDeleteTopic()
  const onDelete = async () => {
    if (!confirm(`Delete topic "${topic.name}"? All keys and messages will be removed.`)) return
    try {
      await deleteMut.mutateAsync(topic.name)
      toast.success(`Deleted ${topic.name}`)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="truncate font-mono text-base">{topic.name}</CardTitle>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Topic menu">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={onOpen}>
                <ExternalLink className="h-4 w-4 mr-2" /> Open
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={onDelete} className="text-destructive">
                <Trash2 className="h-4 w-4 mr-2" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        {topic.description && (
          <CardDescription className="line-clamp-2">{topic.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex-1">
        <div className="flex gap-2 flex-wrap">
          <Badge variant="outline" className="font-mono">p{topic.default_priority}</Badge>
          <Badge variant="secondary">{topic.retention_days}d retention</Badge>
        </div>
      </CardContent>
      <CardFooter className="justify-between text-xs text-muted-foreground">
        <span>updated {formatRelative(topic.updated_at)}</span>
        <Link to={`/topics/${encodeURIComponent(topic.name)}`} className="hover:underline">
          Open →
        </Link>
      </CardFooter>
    </Card>
  )
}

function NewTopicDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateTopic()
  const [name, setName] = React.useState('')
  const [description, setDescription] = React.useState('')
  const [priority, setPriority] = React.useState(3)
  const [retention, setRetention] = React.useState(7)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!open) {
      setName('')
      setDescription('')
      setPriority(3)
      setRetention(7)
      setError(null)
    }
  }, [open])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const t = await create.mutateAsync({
        name: name.trim(),
        description: description.trim() || null,
        default_priority: priority,
        retention_days: retention,
      })
      toast.success(`Created ${t.name}`)
      onClose()
    } catch (e) {
      const err = e as Error & { status?: number }
      if (err.status === 409) setError('A topic with that name already exists')
      else if (err.status === 422) setError('Invalid name (letters, digits, underscore, dash only; max 120 chars)')
      else setError(err.message || 'Failed to create topic')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New topic</DialogTitle>
          <DialogDescription>Publish-and-subscribe channel for your account.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="t-name">Name</Label>
            <Input
              id="t-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={120}
              pattern="[A-Za-z0-9_-]+"
              placeholder="alerts"
            />
            <p className="text-xs text-muted-foreground">Letters, digits, underscore, dash. Used in URLs.</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="t-desc">Description (optional)</Label>
            <Input
              id="t-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              placeholder="prod deploy alerts"
            />
          </div>
          <div className="flex gap-4">
            <div className="flex flex-col gap-1.5 flex-1">
              <Label htmlFor="t-prio">Default priority</Label>
              <Select id="t-prio" value={String(priority)} onChange={(e) => setPriority(Number(e.target.value))}>
                <option value="1">1 — min</option>
                <option value="2">2 — low</option>
                <option value="3">3 — default</option>
                <option value="4">4 — high</option>
                <option value="5">5 — max</option>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5 flex-1">
              <Label htmlFor="t-ret">Retention (days)</Label>
              <Input
                id="t-ret"
                type="number"
                min={1}
                max={365}
                value={retention}
                onChange={(e) => setRetention(Number(e.target.value))}
              />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || !name}>
              {create.isPending ? 'Creating…' : 'Create topic'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}