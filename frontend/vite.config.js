import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // A dónde reenvía Vite las peticiones /api/* en desarrollo.
  // Se usa 127.0.0.1 en vez de "localhost": en Linux, Node puede resolver
  // "localhost" a IPv6 (::1) y Flask solo escucha en IPv4 → conexión rechazada.
  const apiTarget = (env.VITE_API_PROXY || 'http://127.0.0.1:5000').replace('localhost', '127.0.0.1')

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      // El front llama a /api/login, /api/facturas... y Vite lo reenvía a Flask
      // quitando el prefijo /api. Mismo origen para el navegador = sin CORS.
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
