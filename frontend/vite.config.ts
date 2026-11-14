import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        dashboard: resolve(__dirname, 'index.html'),
        nenvaCall: resolve(__dirname, 'nenva-call.html'),
      },
    },
  },
})
