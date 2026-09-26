import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

// `npm run dev` proxies the API to a locally running engine
// (python -m curelab --pack ... --port 8000).
export default defineConfig({
  plugins: [preact()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
  },
});
