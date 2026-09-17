import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 开发时把 /api 代理到后端（避免 CORS）
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // WebSocket（迭代4 坐席接管实时推送）—— ws:true 才会转发升级握手
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
