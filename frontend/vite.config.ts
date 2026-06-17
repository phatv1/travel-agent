import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    // Forward API calls to the FastAPI dev server during development.
    proxy: {
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
