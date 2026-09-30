/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// The dashboard talks to the FastAPI backend only, so there is no dev proxy for
// data. VITE_API_BASE_URL / VITE_WS_URL override the defaults for deployments
// where the two are served from different hosts.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiBase = env.VITE_API_BASE_URL ?? 'http://localhost:8000';
  const wsBase = env.VITE_WS_URL ?? apiBase.replace(/^http/, 'ws');

  return {
    plugins: [react()],
    server: { port: Number(env.VITE_PORT ?? 5173), host: true },
    preview: { port: Number(env.VITE_PREVIEW_PORT ?? 4173), host: true },
    build: { outDir: 'dist', sourcemap: false, target: 'es2020' },
    define: {
      __API_BASE_URL__: JSON.stringify(apiBase),
      __WS_URL__: JSON.stringify(wsBase),
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      include: ['src/**/*.test.{ts,tsx}'],
    },
  };
});
