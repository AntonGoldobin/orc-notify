import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Card,
  Input,
  Label,
  Spinner,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
  Typography,
} from '@heroui/react'
import { Topbar } from '../components/Topbar'
import * as rules from '../api/rules'
import { ApiError } from '../api/client'

export default function Rules() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['rules'], queryFn: rules.list })

  const [name, setName] = useState('')
  const [pattern, setPattern] = useState('*')
  const [enabled, setEnabled] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [patternTouched, setPatternTouched] = useState(false)

  const createMut = useMutation({
    mutationFn: () => rules.create({ name, event_pattern: pattern, enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rules'] })
      setName('')
      setPattern('*')
      setEnabled(true)
      setError(null)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) {
        setError('Invalid name or pattern (use a glob like "thread.*" or "*")')
      } else {
        setError('Failed to create rule')
      }
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => rules.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => rules.update(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })

  const patternValid = pattern.length > 0
  const showPatternError = patternTouched && !patternValid

  return (
    <div className="min-h-svh flex flex-col">
      <Topbar />
      <main className="flex-1 p-4 max-w-5xl mx-auto w-full flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Rules</h1>

        <Card className="p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              setPatternTouched(true)
              if (patternValid) createMut.mutate()
            }}
            className="flex flex-wrap items-end gap-3"
          >
            <div className="flex flex-col gap-1.5 min-w-40 flex-1">
              <Label htmlFor="rule-name">Name</Label>
              <Input
                id="rule-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={120}
              />
            </div>
            <div className="flex flex-col gap-1.5 min-w-40 flex-1">
              <Label htmlFor="rule-pattern">Event pattern (glob)</Label>
              <Input
                id="rule-pattern"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                onBlur={() => setPatternTouched(true)}
                required
                placeholder="thread.* or *"
                color={showPatternError ? 'danger' : 'default'}
              />
              {showPatternError && (
                <span className="text-xs text-danger">Pattern cannot be empty</span>
              )}
            </div>
            <Switch isSelected={enabled} onChange={setEnabled}>Enabled</Switch>
            <Button type="submit" variant="primary" isDisabled={createMut.isPending}>
              {createMut.isPending ? 'Creating…' : 'Add rule'}
            </Button>
          </form>
          {error && <Typography className="text-sm text-danger mt-2">{error}</Typography>}
        </Card>

        {isLoading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : !data || data.length === 0 ? (
          <Card className="p-8 text-center text-default-500">No rules yet. Add a rule to start receiving notifications.</Card>
        ) : (
          <Card>
            <Table aria-label="rules">
              <TableHeader>
                <TableColumn>NAME</TableColumn>
                <TableColumn>PATTERN</TableColumn>
                <TableColumn>ENABLED</TableColumn>
                <TableColumn>CREATED</TableColumn>
                <TableColumn>{' '}</TableColumn>
              </TableHeader>
              <TableBody>
                {data.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.name}</TableCell>
                    <TableCell><code className="text-xs">{r.event_pattern}</code></TableCell>
                    <TableCell>
                      <Switch
                        size="sm"
                        isSelected={r.enabled}
                        onChange={(v) => toggleMut.mutate({ id: r.id, enabled: v })}
                        aria-label={`Enable rule ${r.name}`}
                      />
                    </TableCell>
                    <TableCell>{new Date(r.created_at).toLocaleString()}</TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="danger"
                        onPress={() => {
                          if (confirm(`Delete rule "${r.name}"?`)) deleteMut.mutate(r.id)
                        }}
                        isDisabled={deleteMut.isPending}
                      >
                        Delete
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </main>
    </div>
  )
}
