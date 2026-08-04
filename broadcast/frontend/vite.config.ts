import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/gfs': 'http://127.0.0.1:8787',
      '/api/broadcast': 'http://127.0.0.1:8787',
      '/health': 'http://127.0.0.1:8787',
      '/ws': { target: 'ws://127.0.0.1:8787', ws: true },
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        site: resolve(__dirname, 'site.html'),
        gfs: resolve(__dirname, 'index.html'),
        broadcast: resolve(__dirname, 'broadcast.html'),
        watch: resolve(__dirname, 'watch.html'),
      },
    },
  },
});
