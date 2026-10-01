import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The frontend never talks to the API by absolute URL. Everything goes through
// /api/*, so the same build runs against a dev proxy, a reverse proxy, or a
// container network without a rebuild.
const API_TARGET = process.env.KAVAL_API ?? 'http://localhost:8077'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
  build: { outDir: 'dist', sourcemap: true },
})
