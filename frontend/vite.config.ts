import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [react(), tailwindcss(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['pwa-192.svg', 'pwa-512.svg'],
    manifest: {
      name: 'Pennywise Expense Tracker', short_name: 'Pennywise', description: 'A calm home for everyday spending.', theme_color: '#18332f', background_color: '#f5f4ef', display: 'standalone', start_url: '/dashboard',
      icons: [{ src: 'pwa-192.svg', sizes: '192x192', type: 'image/svg+xml' }, { src: 'pwa-512.svg', sizes: '512x512', type: 'image/svg+xml' }],
    },
  })],
})