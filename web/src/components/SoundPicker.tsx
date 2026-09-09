import * as React from 'react'
import { Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useSounds } from '@/hooks/useSounds'
import { useUpdateTopic } from '@/hooks/useTopics'
import { playSound, unlockAudio } from '@/lib/sounds'

interface SoundPickerProps {
  topicName: string
  currentSoundId: string | null
}

/**
 * Per-topic sound selector. Lists "(none)" + the user's library and persists
 * the choice via the topic-update mutation (sending explicit `null` detaches).
 */
export function SoundPicker({ topicName, currentSoundId }: SoundPickerProps) {
  const { data: sounds } = useSounds()
  const updateTopic = useUpdateTopic(topicName)
  const [value, setValue] = React.useState<string>(currentSoundId ?? '')

  // Sync the local value when the topic changes server-side.
  React.useEffect(() => {
    setValue(currentSoundId ?? '')
  }, [currentSoundId])

  const onChange = async (next: string) => {
    setValue(next)
    // Sending explicit `null` detaches; empty string == "(none)" == null.
    const sound_id = next === '' ? null : next
    try {
      await updateTopic.mutateAsync({ sound_id })
    } catch (e) {
      // Revert local value on failure.
      setValue(currentSoundId ?? '')
      throw e
    }
  }

  const onTest = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    unlockAudio()
    if (value === '') return
    const url = (sounds ?? []).find((s) => s.id === value)?.url
    if (url) playSound(url)
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="topic-sound">Notification sound</Label>
      <div className="flex gap-2">
        <Select
          id="topic-sound"
          value={value}
          onChange={(e) => {
            void onChange(e.target.value)
          }}
          disabled={updateTopic.isPending}
        >
          <option value="">(none)</option>
          {(sounds ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
        <Button type="button" variant="outline" size="icon" onClick={onTest} disabled={value === ''} aria-label="Test sound">
          <Play className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
