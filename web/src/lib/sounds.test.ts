import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BUILTIN_SOUNDS, isMuted, playSound, setMuted } from './sounds'

const instances: FakeAudio[] = []

class FakeAudio {
  src: string
  currentTime = 0
  preload = ''
  volume = 1
  play: ReturnType<typeof vi.fn>
  constructor(src: string) {
    this.src = src
    this.play = vi.fn().mockResolvedValue(undefined)
    instances.push(this)
  }
}

let n = 0
const unique = (label: string) => `/sounds/${label}-${++n}.wav`

describe('sounds lib', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    instances.length = 0
    vi.stubGlobal('Audio', FakeAudio)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('exports BUILTIN_SOUNDS pointing at /sounds/*.wav', () => {
    expect(BUILTIN_SOUNDS.length).toBeGreaterThanOrEqual(4)
    for (const s of BUILTIN_SOUNDS) {
      expect(s.url).toMatch(/^\/sounds\/.+\.wav$/)
      expect(s.name).toBeTruthy()
    }
  })

  it('isMuted / setMuted round-trip via localStorage', () => {
    expect(isMuted()).toBe(false)
    setMuted(true)
    expect(isMuted()).toBe(true)
    expect(localStorage.getItem('app-sounds-muted')).toBe('1')
    setMuted(false)
    expect(isMuted()).toBe(false)
    expect(localStorage.getItem('app-sounds-muted')).toBe('0')
  })

  it('playSound constructs Audio with the right src', () => {
    const url = unique('chime')
    playSound(url)
    expect(instances).toHaveLength(1)
    expect(instances[0].src).toBe(url)
    expect(instances[0].play).toHaveBeenCalledTimes(1)
  })

  it('playSound reuses cached Audio on repeat calls', () => {
    const url = unique('chime')
    playSound(url)
    playSound(url)
    // Same URL → cached, no new instance.
    expect(instances).toHaveLength(1)
  })

  it('playSound is a no-op when muted', () => {
    setMuted(true)
    playSound(unique('chime'))
    expect(instances).toHaveLength(0)
  })

  it('playSound swallows play() rejections silently', () => {
    const url = unique('chime')
    playSound(url)
    // Replace the play() on the cached instance with one that rejects.
    // playSound() catches the rejection internally → no unhandled rejection,
    // no throw to the caller.
    const inst = instances[0] as unknown as { play: () => Promise<void> }
    inst.play = () => Promise.reject(new Error('Autoplay blocked'))
    expect(() => playSound(url)).not.toThrow()
  })
})
