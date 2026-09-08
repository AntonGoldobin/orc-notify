import * as React from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Bell, Copy, Loader2, MessageSquare, Send, Settings as SettingsIcon, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch as _Switch } from '@/components/ui/switch' // kept for future per-key toggles
void _Switch
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useTopic, useUpdateTopic, useDeleteTopic } from '@/hooks/useTopics'
import { useCreateTopicKey, useDeleteTopicKey, usePatchTopicKey, useTopicKeys } from '@/hooks/useTopicKeys'
import { useLiveMessages, useMessages } from '@/hooks/useMessages'
import { usePublishMessage } from '@/hooks/usePublishMessage'
import { subscribeTopic } from '@/api/messages'
import { formatRelative } from '@/lib/utils'
import { toast } from 'sonner'
import type { MessageOut, TopicKeyCreatedOut } from '@/api/types'

type Tab = 'messages' | 'publish' | 'settings'

function tabFromPath(tab: string | undefined): Tab {
  if (tab === 'publish' || tab === 'settings') return tab
  return 'messages'
}

export default function TopicDetailPage() {
  const { name, tab } = useParams<{ name: string; tab?: string }>()
  const navigate = useNavigate()
  const topicName = name ?? ''
  const currentTab = tabFromPath(tab)

  const { data: topic, isLoading } = useTopic(topicName)
  const updateTopic = useUpdateTopic(topicName)
  const deleteTopic = useDeleteTopic()

  if (!name) return <Navigate to="/topics" replace />

  const setTab = (next: Tab) => {
    if (next === 'messages') navigate(`/topics/${encodeURIComponent(topicName)}`, { replace: true })
    else navigate(`/topics/${encodeURIComponent(topicName)}/${next}`, { replace: true })
  }

  return (
    <div className="mx-auto max-w-6xl flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Button asChild variant="ghost" size="icon">
            <Link to="/topics" aria-label="Back to topics">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          {isLoading ? (
            <Skeleton className="h-7 w-40" />
          ) : topic ? (
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold font-mono truncate">{topic.name}</h1>
              {topic.description && (
                <p className="text-sm text-muted-foreground">{topic.description}</p>
              )}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Topic not found</div>
          )}
        </div>
        {topic && (
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono">p{topic.default_priority}</Badge>
            <Badge variant="secondary">{topic.retention_days}d</Badge>
            <Button
              variant="destructive"
              size="sm"
              onClick={async () => {
                if (!confirm(`Delete topic "${topic.name}"?`)) return
                try {
                  await deleteTopic.mutateAsync(topic.name)
                  toast.success('Topic deleted')
                  navigate('/topics', { replace: true })
                } catch (e) {
                  toast.error((e as Error).message)
                }
              }}
            >
              <Trash2 className="h-4 w-4 mr-1" /> Delete
            </Button>
          </div>
        )}
      </div>

      <Tabs value={currentTab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="messages">
            <MessageSquare className="h-4 w-4 mr-2" /> Messages
          </TabsTrigger>
          <TabsTrigger value="publish">
            <Send className="h-4 w-4 mr-2" /> Publish
          </TabsTrigger>
          <TabsTrigger value="settings">
            <SettingsIcon className="h-4 w-4 mr-2" /> Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="messages">
          <MessagesTab topic={topicName} />
        </TabsContent>
        <TabsContent value="publish">
          <PublishTab topic={topicName} defaultPriority={topic?.default_priority ?? 3} />
        </TabsContent>
        <TabsContent value="settings">
          <SettingsTab
            topic={topic}
            isLoading={isLoading}
            onSave={async (patch) => {
              try {
                await updateTopic.mutateAsync(patch)
                toast.success('Topic updated')
              } catch (e) {
                toast.error((e as Error).message)
              }
            }}
            saving={updateTopic.isPending}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ── Messages tab (SSE live tail + initial fetch) ─────────────────────────

function MessagesTab({ topic }: { topic: string }) {
  const { data: messages, isLoading } = useMessages(topic, { limit: 200 })
  const onLive = useLiveMessages(topic)
  const [connected, setConnected] = React.useState(false)

  React.useEffect(() => {
    const handle = subscribeTopic(topic, (evt) => {
      if (evt.type === 'ready') setConnected(true)
      else if (evt.type === 'message') onLive(evt.data)
      else if (evt.type === 'error') setConnected(false)
    })
    return () => handle.close()
  }, [topic, onLive])

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Messages</CardTitle>
          <Badge variant={connected ? 'default' : 'outline'} className="font-mono">
            {connected ? 'LIVE' : 'offline'}
          </Badge>
        </div>
        <CardDescription>Live SSE tail. Older messages via GET /{topic}/json.</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : !messages || messages.length === 0 ? (
          <div className="text-sm text-muted-foreground p-8 text-center">
            No messages yet. Publish via the <Link to={`/topics/${encodeURIComponent(topic)}/publish`} className="underline">Publish tab</Link> or curl.
          </div>
        ) : (
          <ScrollArea className="h-[480px]">
            <ul className="flex flex-col divide-y">
              {messages.map((m) => (
                <MessageRow key={m.id} msg={m} />
              ))}
            </ul>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}

function MessageRow({ msg }: { msg: MessageOut }) {
  return (
    <li className="flex flex-col gap-1 py-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono">p{msg.priority}</Badge>
          {msg.title && <span className="font-medium text-foreground">{msg.title}</span>}
          {msg.tags.map((t) => (
            <Badge key={t} variant="secondary" className="font-mono">
              {t}
            </Badge>
          ))}
        </div>
        <span>{formatRelative(msg.time * 1000)}</span>
      </div>
      <pre className="whitespace-pre-wrap break-words text-sm font-mono">{msg.message}</pre>
    </li>
  )
}

// ── Publish tab (form + curl example) ────────────────────────────────────

function PublishTab({ topic, defaultPriority }: { topic: string; defaultPriority: number }) {
  const publishMut = usePublishMessage(topic)
  const [title, setTitle] = React.useState('')
  const [body, setBody] = React.useState('')
  const [priority, setPriority] = React.useState(defaultPriority)
  const [tags, setTags] = React.useState('')
  const [click, setClick] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)

  const curl = buildCurl({ topic, title, body, priority, tags, click })

  const onPublish = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const r = await publishMut.mutateAsync({
        title: title || undefined,
        body,
        priority,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : undefined,
        click: click || undefined,
        content_type: 'text/plain',
      })
      toast.success(r.created ? 'Published' : 'Already published (idempotent hit)')
      setBody('')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const copyCurl = async () => {
    await navigator.clipboard.writeText(curl)
    toast.success('Copied curl to clipboard')
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Publish</CardTitle>
          <CardDescription>Send a message to <code className="font-mono">{topic}</code></CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onPublish} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="p-title">Title</Label>
              <Input id="p-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="flex gap-3">
              <div className="flex flex-col gap-1.5 flex-1">
                <Label htmlFor="p-prio">Priority</Label>
                <Select id="p-prio" value={String(priority)} onChange={(e) => setPriority(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((p) => (
                    <option key={p} value={String(p)}>{p}</option>
                  ))}
                </Select>
              </div>
              <div className="flex flex-col gap-1.5 flex-1">
                <Label htmlFor="p-tags">Tags (CSV)</Label>
                <Input id="p-tags" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="rotating_light,deploy" />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="p-click">Click URL</Label>
              <Input id="p-click" value={click} onChange={(e) => setClick(e.target.value)} placeholder="https://example.com/run/123" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="p-body">Body</Label>
              <Textarea id="p-body" value={body} onChange={(e) => setBody(e.target.value)} required rows={5} />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={publishMut.isPending || !body}>
              {publishMut.isPending ? 'Publishing…' : 'Publish'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>curl example</CardTitle>
            <Button size="sm" variant="ghost" onClick={copyCurl}>
              <Copy className="h-4 w-4 mr-1" /> Copy
            </Button>
          </div>
          <CardDescription>One-shot command. Auth via session cookie.</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="text-xs bg-muted p-3 rounded overflow-x-auto whitespace-pre">
{curl}
          </pre>
        </CardContent>
      </Card>
    </div>
  )
}

function buildCurl({
  topic,
  title,
  body,
  priority,
  tags,
  click,
}: {
  topic: string
  title: string
  body: string
  priority: number
  tags: string
  click: string
}) {
  const lines: string[] = [`curl -X POST https://orc-notify.orc.golden-antelope.ru/${encodeURIComponent(topic)} \\`]
  lines.push(`  -H "Content-Type: text/plain" \\`)
  if (title) lines.push(`  -H "Title: ${title.replace(/"/g, '\\"')}" \\`)
  lines.push(`  -H "Priority: ${priority}" \\`)
  if (tags) lines.push(`  -H "Tags: ${tags}" \\`)
  if (click) lines.push(`  -H "Click: ${click}" \\`)
  lines.push(`  --cookie-jar cookies.txt \\`)
  lines.push(`  --cookie cookies.txt \\`)
  lines.push(`  -d ${JSON.stringify(body || 'Hello from curl')}`)
  return lines.join('\n')
}

// ── Settings tab ─────────────────────────────────────────────────────────

function SettingsTab({
  topic,
  isLoading,
  onSave,
  saving,
}: {
  topic: ReturnType<typeof useTopic>['data']
  isLoading: boolean
  onSave: (patch: { description: string | null; default_priority: number; retention_days: number }) => void
  saving: boolean
}) {
  const [description, setDescription] = React.useState(topic?.description ?? '')
  const [priority, setPriority] = React.useState(topic?.default_priority ?? 3)
  const [retention, setRetention] = React.useState(topic?.retention_days ?? 7)

  React.useEffect(() => {
    if (topic) {
      setDescription(topic.description ?? '')
      setPriority(topic.default_priority)
      setRetention(topic.retention_days)
    }
  }, [topic])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Topic settings</CardTitle>
          <CardDescription>Update description, default priority, and retention.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading || !topic ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                onSave({ description: description || null, default_priority: priority, retention_days: retention })
              }}
              className="flex flex-col gap-3"
            >
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="s-desc">Description</Label>
                <Input id="s-desc" value={description ?? ''} onChange={(e) => setDescription(e.target.value)} maxLength={500} />
              </div>
              <div className="flex gap-3">
                <div className="flex flex-col gap-1.5 flex-1">
                  <Label htmlFor="s-prio">Default priority</Label>
                  <Select id="s-prio" value={String(priority)} onChange={(e) => setPriority(Number(e.target.value))}>
                    {[1, 2, 3, 4, 5].map((p) => (
                      <option key={p} value={String(p)}>{p}</option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5 flex-1">
                  <Label htmlFor="s-ret">Retention (days)</Label>
                  <Input
                    id="s-ret"
                    type="number"
                    min={1}
                    max={365}
                    value={retention}
                    onChange={(e) => setRetention(Number(e.target.value))}
                  />
                </div>
              </div>
              <Button type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <KeysCard topic={topic?.name ?? ''} />
    </div>
  )
}

function KeysCard({ topic }: { topic: string }) {
  const { data: keys, isLoading } = useTopicKeys(topic)
  const createMut = useCreateTopicKey(topic)
  const patchMut = usePatchTopicKey(topic)
  const deleteMut = useDeleteTopicKey(topic)
  const [showSecret, setShowSecret] = React.useState<{ keyName: string; secret: string } | null>(null)
  const [newName, setNewName] = React.useState('')

  const onCreate = async () => {
    if (!newName.trim()) return
    try {
      const res: TopicKeyCreatedOut = await createMut.mutateAsync({ name: newName.trim() })
      setNewName('')
      if (res.secret) setShowSecret({ keyName: res.name, secret: res.secret })
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const onRotate = async (keyId: string, name: string) => {
    try {
      const res = await patchMut.mutateAsync({ keyId, patch: {} })
      if (res.secret) setShowSecret({ keyName: name, secret: res.secret })
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const onDelete = async (keyId: string, name: string) => {
    if (!confirm(`Delete key "${name}"?`)) return
    try {
      await deleteMut.mutateAsync(keyId)
      toast.success('Key deleted')
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Topic keys</CardTitle>
        <CardDescription>Bearer tokens with publish/read scopes.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2 mb-3">
          <Input
            placeholder="key name (e.g. ci-deploy)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            maxLength={120}
          />
          <Button onClick={onCreate} disabled={createMut.isPending || !newName.trim()}>
            Create
          </Button>
        </div>

        {isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : !keys || keys.length === 0 ? (
          <p className="text-sm text-muted-foreground p-4 text-center border rounded">No keys yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>NAME</TableHead>
                <TableHead>SCOPES</TableHead>
                <TableHead>CREATED</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.map((k) => (
                <TableRow key={k.id}>
                  <TableCell className="font-medium">{k.name}</TableCell>
                  <TableCell className="font-mono text-xs">{k.scopes}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatRelative(k.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">…</Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => onRotate(k.id, k.name)}>
                          Rotate (returns new secret)
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => onDelete(k.id, k.name)} className="text-destructive">
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

      <Dialog open={showSecret !== null} onOpenChange={(v) => !v && setShowSecret(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save your key secret</DialogTitle>
            <DialogDescription>This is the only time the secret will be shown.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label>Key: {showSecret?.keyName}</Label>
            <div className="flex gap-2">
              <Input readOnly value={showSecret?.secret ?? ''} className="font-mono text-xs" />
              <Button
                variant="secondary"
                onClick={async () => {
                  if (showSecret?.secret) {
                    await navigator.clipboard.writeText(showSecret.secret)
                    toast.success('Copied')
                  }
                }}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setShowSecret(null)}>I have saved it</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </CardContent>
    </Card>
  )
}

// suppress unused import warnings (Bell is used elsewhere)
void Bell