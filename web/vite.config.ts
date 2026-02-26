import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// When running inside Docker, VITE_BACKEND_URL is injected by docker-compose.
// For local development outside Docker, we fall back to localhost:8000.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "../", "");

  const backendUrl = env.VITE_BACKEND_URL ?? "http://localhost:8000";
  const wsUrl = backendUrl.replace(/^http/, "ws");

  return {
    plugins: [react()],
    envDir: "../",
    server: {
      host: "0.0.0.0",   // expose to host machine when running in Docker
      port: 3000,
      proxy: {
        // Proxy API calls to FastAPI backend
        "/api": {
          target: backendUrl,
          changeOrigin: true,
        },
        // Proxy WebSocket connections to FastAPI backend
        "/ws": {
          target: wsUrl,
          ws: true,
          changeOrigin: true,
        },
      },
    },
  };
});
