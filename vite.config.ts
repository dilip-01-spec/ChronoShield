import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// The dev server proxies /backend/* to the FastAPI gateway so the browser never
// hits CORS during development. Set VITE_API_BASE_URL to a full URL to bypass it.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    build: { chunkSizeWarningLimit: 900 },
    server: {
      proxy: {
        '/backend': {
          target,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/backend/, ''),
        },
      },
    },
    preview: {
      proxy: {
        '/backend': {
          target,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/backend/, ''),
        },
      },
    },
  }
})
