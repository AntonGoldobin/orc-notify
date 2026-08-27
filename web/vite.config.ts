/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin proxy → FastAPI backend. Backend has NO CORS middleware.
    // In production, the Captain app orc-notify-web will reverse_proxy these paths
    // to srv-captain--orc-notify:8000. E2E tests can override via E2E_API_BASE.
    proxy: {
      '/auth': {
        target: process.env.VITE_API_BASE ?? 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/api': {
        target: process.env.VITE_API_BASE ?? 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/v1': {
        target: process.env.VITE_API_BASE ?? 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: false,
      },
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'e2e/**'],
  },
})
