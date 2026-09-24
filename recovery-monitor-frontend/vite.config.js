import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The UI calls relative /api/... URLs. In development Vite forwards them to the local backend;
// in the demo build the backend serves this app itself, so no CORS and no hardcoded host.
const target = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, proxy: { '/api': { target, changeOrigin: true } } },
  preview: { proxy: { '/api': { target, changeOrigin: true } } },
});
