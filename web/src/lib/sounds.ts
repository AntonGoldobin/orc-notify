/**
 * Audio playback for per-topic notification sounds.
 *
 * Browsers refuse programmatic Audio without a prior user gesture. We work
 * around that by playing a single silent preset on the first user click —
 * `unlockAudio()`. After that, `playSound()` works for the tab's lifetime.
 *
 * Sound URLs are served from `/sounds/*.wav` (public dir) or from the user's
 * library at arbitrary URLs. We cache one HTMLAudioElement per URL so repeat
 * notifications cut off cleanly without a re-fetch.
 */

const MUTED_KEY = 'app-sounds-muted'
const UNLOCK_KEY = '__audio_unlocked'

export interface BuiltinSound {
  name: string
  url: string
}

export const BUILTIN_SOUNDS: BuiltinSound[] = [
  { name: 'Chime', url: '/sounds/chime.wav' },
  { name: 'Bell', url: '/sounds/bell.wav' },
  { name: 'Pop', url: '/sounds/pop.wav' },
  { name: 'Alert', url: '/sounds/alert.wav' },
]

const cache = new Map<string, HTMLAudioElement>()

function getAudio(url: string): HTMLAudioElement {
  let el = cache.get(url)
  if (!el) {
    el = new Audio(url)
    el.preload = 'auto'
    cache.set(url, el)
  }
  return el
}

export function isMuted(): boolean {
  return localStorage.getItem(MUTED_KEY) === '1'
}

export function setMuted(v: boolean): void {
  localStorage.setItem(MUTED_KEY, v ? '1' : '0')
}

export function playSound(url: string): void {
  if (isMuted()) return
  const el = getAudio(url)
  try {
    el.currentTime = 0
    void el.play().catch(() => {
      // Autoplay blocked or audio failed — silent no-op.
    })
  } catch {
    // Some browsers throw synchronously on play(); ignore.
  }
}

/**
 * Play one silent preset to satisfy the browser's autoplay gate.
 * Guarded so it only runs once per tab. Safe to call from any user gesture
 * (click, keydown). If already unlocked, this is a no-op.
 */
export function unlockAudio(): void {
  if (sessionStorage.getItem(UNLOCK_KEY) === '1') return
  const silent = new Audio(BUILTIN_SOUNDS[0].url)
  silent.volume = 0
  silent.play()
    .then(() => {
      sessionStorage.setItem(UNLOCK_KEY, '1')
    })
    .catch(() => {
      // Still gated — try again on the next gesture.
    })
}
