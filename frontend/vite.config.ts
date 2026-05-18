import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // App is served at /dashboard/* by FastAPI StaticFiles mount in echo/main.py.
  // Without this base, asset URLs in index.html resolve to /assets/* (404 in prod).
  base: "/dashboard/",
  build: {
    outDir: "../echo/static/dashboard",
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8004",
        changeOrigin: true,
      },
    },
  },
});
