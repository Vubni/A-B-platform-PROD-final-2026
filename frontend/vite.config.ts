import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const backendPort = env.BACKEND_PORT || '18080'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/__api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/__api/, ''),
        },
      },
    },
  }
})
