import * as React from 'react'
import { subscribe } from '@/api/events'
import { useTopics } from '@/hooks/useTopics'
import { playSound } from '@/lib/sounds'

/**
 * Mount-once global SSE listener. Lives for the whole authed session across
 * route changes. Plays the topic's assigned sound on every incoming
 * notification, no matter which page is open. Also broadcasts the same
 * `sse-status` window CustomEvent TopicDetail emits, so the footer Live/Offline
 * badge works on every page (not only the topic detail view).
 *
 * Sound playback is OWNED exclusively by this hook. TopicDetail's per-topic
 * stream is for cache injection only — never plays sounds.
 */
export function useGlobalSSE(): void {
  const { data: topics } = useTopics()
  // Ref keeps the live topic map without making the effect depend on it.
  // Otherwise every topics cache update would tear down + reopen the EventSource,
  // dropping notifications in flight.
  const topicsRef = React.useRef(topics)
  React.useEffect(() => {
    topicsRef.current = topics
  }, [topics])

  React.useEffect(() => {
    const emit = (s: 'open' | 'closed') =>
      window.dispatchEvent(new CustomEvent('sse-status', { detail: s }))
    emit('open')
    const handle = subscribe((evt) => {
      if (evt.type === 'ready') {
        emit('open')
      } else if (evt.type === 'notification') {
        const topicId = evt.data.topic_id
        if (!topicId) return
        const t = topicsRef.current?.find((x) => x.id === topicId)
        if (t?.sound?.url) playSound(t.sound.url)
      } else if (evt.type === 'error') {
        emit('closed')
      }
    })
    return () => {
      handle.close()
      emit('closed')
    }
    // Empty deps → mount once per AuthProvider lifetime (layout is authed-only).
    // Topics are read via ref.
  }, [])
}
