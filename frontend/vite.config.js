import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/plan': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        bypass: (request) => request.method === 'GET' && request.url === '/plan' ? '/index.html' : undefined,
      },
      '/api/v1': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
