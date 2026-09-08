/**
 * Global Keys page (legacy `/keys` URL — kept for backward compat with
 * bookmarks from the HeroUI SPA). Shows topic keys across all topics in a
 * flat table. Phase 4 cutover removes this page; users should manage keys
 * per-topic from the Settings tab of each topic.
 */
import { Link as RouterLink } from 'react-router-dom'
import { KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useTopics } from '@/hooks/useTopics'
import { useTopicKeys } from '@/hooks/useTopicKeys'
import { formatRelative } from '@/lib/utils'

export default function KeysPage() {
  const { data: topics, isLoading } = useTopics()

  return (
    <div className="mx-auto max-w-5xl flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Keys</h1>
          <p className="text-sm text-muted-foreground">
            All keys across all your topics. Manage keys per-topic in the topic's Settings tab.
          </p>
        </div>
        <Button asChild>
          <RouterLink to="/topics">
            <KeyRound className="h-4 w-4 mr-1" /> Manage per-topic
          </RouterLink>
        </Button>
      </div>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !topics || topics.length === 0 ? (
        <Card className="p-8 text-center text-muted-foreground">
          No topics yet. Create a topic to start adding keys.
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>All keys</CardTitle>
            <CardDescription>
              Cross-topic view. For management actions, use the per-topic Settings tab.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>TOPIC</TableHead>
                  <TableHead>KEY NAME</TableHead>
                  <TableHead>SCOPES</TableHead>
                  <TableHead>CREATED</TableHead>
                  <TableHead>LAST USED</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topics.map((t) => (
                  <KeysForTopicRow key={t.id} topic={t.name} />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function KeysForTopicRow({ topic }: { topic: string }) {
  const { data: keys } = useTopicKeys(topic)
  if (!keys || keys.length === 0) {
    return (
      <TableRow>
        <TableCell className="font-mono text-xs">{topic}</TableCell>
        <TableCell colSpan={4} className="text-muted-foreground text-xs italic">
          no keys
        </TableCell>
      </TableRow>
    )
  }
  return (
    <>
      {keys.map((k) => (
        <TableRow key={k.id}>
          <TableCell className="font-mono text-xs">{topic}</TableCell>
          <TableCell>{k.name}</TableCell>
          <TableCell className="font-mono text-xs">{k.scopes}</TableCell>
          <TableCell className="text-xs text-muted-foreground">{formatRelative(k.created_at)}</TableCell>
          <TableCell className="text-xs text-muted-foreground">
            {k.last_used_at ? formatRelative(k.last_used_at) : '—'}
          </TableCell>
        </TableRow>
      ))}
    </>
  )
}