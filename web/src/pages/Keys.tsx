import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Card,
  Chip,
  Input,
  Label,
  Modal,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
  Typography,
  useOverlayState,
} from '@heroui/react'
import { Topbar } from '../components/Topbar'
import * as keys from '../api/keys'
import { ApiError } from '../api/client'
import type { AgentCreatedOut } from '../api/types'

export default function Keys() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({ queryKey: ['keys'], queryFn: keys.list })

  const createState = useOverlayState()
  const [createdSecret, setCreatedSecret] = useState<{ name: string; agentId: string; secret: string } | null>(null)

  const removeMut = useMutation({
    mutationFn: (id: string) => keys.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['keys'] }),
  })
  const rotateMut = useMutation({
    mutationFn: (id: string) => keys.rotate(id),
    onSuccess: (res: AgentCreatedOut) => {
      qc.invalidateQueries({ queryKey: ['keys'] })
      setCreatedSecret({ name: res.name, agentId: res.agent_id, secret: res.webhook_secret ?? '' })
    },
  })

  return (
    <div className="min-h-svh flex flex-col">
      <Topbar />
      <main className="flex-1 p-4 max-w-5xl mx-auto w-full">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-semibold">Agents</h1>
          <Button variant="primary" onPress={createState.open}>New agent</Button>
        </div>

        {error && <Card className="p-4 text-danger mb-4">Failed to load agents.</Card>}

        {isLoading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : !data || data.length === 0 ? (
          <Card className="p-8 text-center text-default-500">No agents yet. Create one to start receiving webhooks.</Card>
        ) : (
          <Card>
            <Table aria-label="agents">
              <TableHeader>
                <TableColumn>NAME</TableColumn>
                <TableColumn>AGENT ID</TableColumn>
                <TableColumn>CREATED</TableColumn>
                <TableColumn>LAST EVENT</TableColumn>
                <TableColumn>{' '}</TableColumn>
              </TableHeader>
              <TableBody>
                {data.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>{a.name}</TableCell>
                    <TableCell><code className="text-xs">{a.agent_id}</code></TableCell>
                    <TableCell>{new Date(a.created_at).toLocaleString()}</TableCell>
                    <TableCell>{a.last_event_at ? new Date(a.last_event_at).toLocaleString() : '—'}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="secondary"
                          onPress={() => rotateMut.mutate(a.agent_id)}
                          isDisabled={rotateMut.isPending}
                        >
                          Rotate
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onPress={() => {
                            if (confirm(`Delete agent "${a.name}"?`)) removeMut.mutate(a.agent_id)
                          }}
                          isDisabled={removeMut.isPending}
                        >
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </main>

      <Modal state={createState}>
        <Modal.Backdrop>
          <Modal.Container>
            <Modal.Dialog>
              <CreateAgentModalContent
                onCancel={createState.close}
                onCreated={(res) => {
                  createState.close()
                  qc.invalidateQueries({ queryKey: ['keys'] })
                  setCreatedSecret({ name: res.name, agentId: res.agent_id, secret: res.webhook_secret ?? '' })
                }}
              />
            </Modal.Dialog>
          </Modal.Container>
        </Modal.Backdrop>
      </Modal>

      <SecretModal
        data={createdSecret}
        onClose={() => setCreatedSecret(null)}
      />
    </div>
  )
}

function CreateAgentModalContent({
  onCancel,
  onCreated,
}: {
  onCancel: () => void
  onCreated: (res: AgentCreatedOut) => void
}) {
  const [name, setName] = useState('')
  const [agentId, setAgentId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await keys.create({ name, agent_id: agentId || undefined })
      onCreated(res)
      setName('')
      setAgentId('')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('Agent ID is already taken')
      } else {
        setError('Failed to create agent')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Modal.Header>
        <Modal.Heading>New agent</Modal.Heading>
      </Modal.Header>
      <Modal.Body className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="agent-name">Name</Label>
          <Input
            id="agent-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={120}
            disabled={submitting}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="agent-id">Agent ID (optional — auto if blank)</Label>
          <Input
            id="agent-id"
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            maxLength={255}
            disabled={submitting}
          />
        </div>
        {error && <Typography className="text-sm text-danger">{error}</Typography>}
      </Modal.Body>
      <Modal.Footer className="flex gap-2 justify-end">
        <Button variant="secondary" onPress={onCancel} isDisabled={submitting}>Cancel</Button>
        <Button variant="primary" onPress={submit} isDisabled={submitting || !name}>
          {submitting ? 'Creating…' : 'Create'}
        </Button>
      </Modal.Footer>
    </>
  )
}

function SecretModal({
  data,
  onClose,
}: {
  data: { name: string; agentId: string; secret: string } | null
  onClose: () => void
}) {
  const state = useOverlayState({ isOpen: data !== null, onOpenChange: (v) => !v && onClose() })
  const copy = () => navigator.clipboard?.writeText(data?.secret ?? '')

  return (
    <Modal state={state}>
      <Modal.Backdrop>
        <Modal.Container>
          <Modal.Dialog>
            <Modal.Header>
              <Modal.Heading>Save your webhook secret</Modal.Heading>
            </Modal.Header>
            <Modal.Body className="flex flex-col gap-3">
              <Chip color="warning" variant="soft">
                This is the only time the secret will be shown. Copy it now.
              </Chip>
              {data && (
                <>
                  <div>
                    <Typography className="text-xs text-default-500">Agent</Typography>
                    <Typography className="text-sm">{data.name} <code className="text-xs">({data.agentId})</code></Typography>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label>Webhook secret</Label>
                    <div className="flex gap-2">
                      <Input value={data.secret} readOnly fullWidth />
                      <Button variant="secondary" onPress={copy}>Copy</Button>
                    </div>
                  </div>
                </>
              )}
            </Modal.Body>
            <Modal.Footer className="flex justify-end">
              <Button variant="primary" onPress={state.close}>I have saved it</Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  )
}
