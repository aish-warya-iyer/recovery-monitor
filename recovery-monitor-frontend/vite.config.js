import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The UI calls relative /api/... URLs. In development Vite forwards them to the local backend;
// in the demo build the backend serves this app itself, so no CORS and no hardcoded host.
const target = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000';
const allowedHosts = (process.env.VITE_ALLOWED_HOSTS || 'zgx-9492.tail2acaa4.ts.net,zgx-9492.tail2dcaa4.ts.net')
  .split(',')
  .map((host) => host.trim())
  .filter(Boolean);

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, allowedHosts, proxy: { '/api': { target, changeOrigin: true } } },
  preview: { allowedHosts, proxy: { '/api': { target, changeOrigin: true } } },
});
