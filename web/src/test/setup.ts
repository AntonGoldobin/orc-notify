import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})

// jsdom doesn't implement matchMedia — needed by ThemeToggle.
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addEventListenerOnce: () => {},
      removeEventListenerOnce: () => {},
      dispatchEvent: () => false,
    }),
  })
}

// jsdom doesn't implement EventSource — subscribe() will throw if called.
// Tests that exercise SSE must stub it explicitly per-test.
if (!globalThis.EventSource) {
  class FakeEventSource {
    url: string
    withCredentials: boolean
    readyState = 0
    onerror: ((e: Event) => void) | null = null
    onopen: ((e: Event) => void) | null = null
    onmessage: ((e: MessageEvent) => void) | null = null
    private listeners: Record<string, Array<(e: Event) => void>> = {}
    constructor(url: string, init?: { withCredentials?: boolean }) {
      this.url = url
      this.withCredentials = !!init?.withCredentials
    }
    addEventListener(type: string, listener: (e: Event) => void) {
      ;(this.listeners[type] ??= []).push(listener)
    }
    removeEventListener() {}
    close() {}
    // Test helper: simulate a server event.
    __emit(type: string, data?: unknown) {
      const evt = data === undefined
        ? new Event(type)
        : new MessageEvent(type, { data: typeof data === 'string' ? data : JSON.stringify(data) })
      ;(this.listeners[type] ?? []).forEach((fn) => fn(evt))
    }
  }
  ;(globalThis as Record<string, unknown>).EventSource = FakeEventSource
}
