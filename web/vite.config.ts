import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    // Talk to the FastAPI backend without CORS in dev: /api/* is proxied.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      // OAuth entry point — the browser follows this straight to Google.
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
