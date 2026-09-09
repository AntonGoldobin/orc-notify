import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Plus, Play, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuth } from '@/auth/AuthProvider'
import { changePassword } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useCreateSound, useDeleteSound, useSounds } from '@/hooks/useSounds'
import { BUILTIN_SOUNDS, playSound, unlockAudio } from '@/lib/sounds'
import { toast } from 'sonner'

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters')
      return
    }
    setSubmitting(true)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      toast.success('Password updated')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError('Current password is incorrect')
      else if (err instanceof ApiError && err.status === 422) setError('Invalid new password (min 8 chars)')
      else setError('Change failed — try again')
    } finally {
      setSubmitting(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="mx-auto max-w-2xl flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>{user?.email}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Account created {user ? new Date(user.created_at).toLocaleString() : '—'}
          </p>
        </CardContent>
      </Card>

      <SoundsCard />

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="current">Current password</Label>
              <Input
                id="current"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                autoComplete="current-password"
                disabled={submitting}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="new">New password</Label>
              <Input
                id="new"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                disabled={submitting}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={submitting} className="self-start">
              {submitting ? 'Saving…' : 'Update password'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={handleLogout}>
            <LogOut className="h-4 w-4 mr-2" /> Log out
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function SoundsCard() {
  const { data: sounds, isLoading } = useSounds()
  const createSound = useCreateSound()
  const deleteSound = useDeleteSound()
  const [addOpen, setAddOpen] = useState(false)

  const onDelete = async (id: string, name: string) => {
    if (!confirm(`Delete sound "${name}"?`)) return
    try {
      await deleteSound.mutateAsync(id)
      toast.success('Sound deleted')
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Sounds</CardTitle>
            <CardDescription>Per-topic notification sounds.</CardDescription>
          </div>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4 mr-1" /> Add sound
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : !sounds || sounds.length === 0 ? (
          <p className="text-sm text-muted-foreground p-4 text-center border rounded">No sounds yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>NAME</TableHead>
                <TableHead>URL</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sounds.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell className="font-mono text-xs truncate max-w-[260px]" title={s.url}>{s.url}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          unlockAudio()
                          playSound(s.url)
                        }}
                        aria-label="Test sound"
                      >
                        <Play className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void onDelete(s.id, s.name)}
                        aria-label="Delete sound"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <AddSoundDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onSubmit={async (input) => {
          try {
            await createSound.mutateAsync(input)
            toast.success('Sound added')
            setAddOpen(false)
          } catch (e) {
            toast.error((e as Error).message)
          }
        }}
        submitting={createSound.isPending}
      />
    </Card>
  )
}

function AddSoundDialog({
  open,
  onOpenChange,
  onSubmit,
  submitting,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onSubmit: (input: { name: string; url: string }) => Promise<void> | void
  submitting: boolean
}) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')

  const reset = () => {
    setName('')
    setUrl('')
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    await onSubmit({ name: name.trim(), url: url.trim() })
    reset()
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange(v) }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add sound</DialogTitle>
          <DialogDescription>Pick a built-in preset or add a custom URL.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3">
          {/* Built-in presets: save the sound in one click. The URL field
              below is only relevant for custom (user-supplied) URLs where
              `type="url"` validation is appropriate. Built-in sounds use
              host-relative paths like `/sounds/chime.wav` that the browser's
              URL validator rejects, so we save them directly here. */}
          <div className="flex flex-col gap-1.5">
            <Label>Built-in presets</Label>
            <div className="grid grid-cols-2 gap-2">
              {BUILTIN_SOUNDS.map((s) => (
                <Button
                  key={s.url}
                  type="button"
                  variant="outline"
                  disabled={submitting}
                  onClick={() => {
                    unlockAudio()
                    playSound(s.url)
                    void onSubmit({ name: s.name, url: s.url })
                  }}
                  className="justify-start"
                >
                  <Play className="h-3 w-3 mr-2" />
                  {s.name}
                </Button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="s-name">Name</Label>
            <Input id="s-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="s-url">URL</Label>
            <Input id="s-url" value={url} onChange={(e) => setUrl(e.target.value)} required type="url" placeholder="https://example.com/sound.wav" />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => { reset(); onOpenChange(false) }}>Cancel</Button>
            <Button type="submit" disabled={submitting || !name.trim() || !url.trim()}>
              {submitting ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
