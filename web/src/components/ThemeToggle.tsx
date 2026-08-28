import { useEffect, useState } from 'react'
import { Button, ButtonGroup } from '@heroui/react'

type Mode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'app-theme'

function applyTheme(mode: Mode) {
  let resolved: 'light' | 'dark'
  if (mode === 'system') {
    resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } else {
    resolved = mode
  }
  document.documentElement.dataset.appTheme = resolved
}

export function ThemeToggle() {
  const [mode, setMode] = useState<Mode>(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as Mode | null
    return saved ?? 'system'
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, mode)
    applyTheme(mode)
  }, [mode])

  // Re-apply when system theme changes (only matters for 'system' mode)
  useEffect(() => {
    if (mode !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme('system')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [mode])

  return (
    <ButtonGroup size="sm">
      <Button variant={mode === 'light' ? 'primary' : 'secondary'} onPress={() => setMode('light')}>Light</Button>
      <Button variant={mode === 'dark' ? 'primary' : 'secondary'} onPress={() => setMode('dark')}>Dark</Button>
      <Button variant={mode === 'system' ? 'primary' : 'secondary'} onPress={() => setMode('system')}>System</Button>
    </ButtonGroup>
  )
}
