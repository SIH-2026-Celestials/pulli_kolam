import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Custom plugin to serve kolam_data from project root
function kolamDataPlugin() {
  const kolamDataPath = path.resolve(__dirname, '../../kolam_data')

  return {
    name: 'kolam-data-server',
    configureServer(server) {
      server.middlewares.use('/kolam_data', (req, res, next) => {
        const filePath = path.join(kolamDataPath, req.url)
        if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
          const ext = path.extname(filePath).toLowerCase()
          const mimeTypes = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
          }
          res.setHeader('Content-Type', mimeTypes[ext] || 'application/octet-stream')
          fs.createReadStream(filePath).pipe(res)
        } else {
          next()
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), kolamDataPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.js'],
    globals: true,
  },
})
