import path from 'node:path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

const BACKEND = 'http://127.0.0.1:8765'

// 伺服器只接受 Host 為 127.0.0.1 / localhost、POST Origin 為本機；
// proxy 不改 Host / Origin（changeOrigin: false），瀏覽器從本機的 dev server 來就會通過。
export default defineConfig({
  plugins: [
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': { target: BACKEND, changeOrigin: false },
      '/media': { target: BACKEND, changeOrigin: false },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
