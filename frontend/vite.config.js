import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue({
      // Every asset the templates reference lives in public/ and is written as
      // an absolute URL. Without this the SFC compiler turns <video src> and
      // <img src> into imports and resolves them from the project root, which
      // fails in dev even when the file is sitting in public/.
      template: { transformAssetUrls: false }
    })
  ],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/socket.io': {
        target: 'http://localhost:5000',
        ws: true
      }
    }
  }
})

