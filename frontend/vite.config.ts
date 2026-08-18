import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Endpoint API backend (FastAPI di 127.0.0.1:8000). Di dev, request ini
// di-proxy ke backend; asset frontend tetap dilayani Vite.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../app/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '^/(documents|deleted-documents|upload|ingest-url|query|sessions|repeated-questions|learning|locations|annotations|glossary|health|metrics|privacy|push)':
        {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      '^/api/glossary': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
