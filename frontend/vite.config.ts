import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Everything the browser needs is served from one origin: the app from Vite, and
// /api (plus the FastAPI docs) proxied through to uvicorn. That keeps CORS out of
// the dev loop and lets the API client use relative URLs, which is also how the
// nginx image serves it in production.
//
// Mirrors scripts/dev.mjs's API_PORT override -- if the default 8000 is stuck
// (e.g. a stale/orphaned listener), `API_PORT=8001 npm run dev` moves uvicorn
// *and* this proxy target together instead of just uvicorn.
const API_PORT = Number(process.env.API_PORT ?? 8000);
const apiTarget = `http://localhost:${API_PORT}`;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Vite matches proxy keys as string prefixes, not path segments -- a
      // bare "/api" would also swallow frontend routes that happen to start
      // with those four letters (e.g. /api-keys), sending them to uvicorn
      // and 404ing instead of serving the SPA. Anchoring on the trailing
      // slash restricts the match to actual /api/* calls.
      "/api/": {
        target: apiTarget,
        changeOrigin: true,
        ws: true, // /api/jobs/{id}/stream is a WebSocket
      },
      "/docs": { target: apiTarget, changeOrigin: true },
      "/openapi.json": { target: apiTarget, changeOrigin: true },
    },
  },
});
