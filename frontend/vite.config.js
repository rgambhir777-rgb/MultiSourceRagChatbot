import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";

// The browser only ever calls the relative path /api. In development, Vite's dev server
// forwards those requests to the Python API, so the browser sees one origin (no CORS).
// In production (Session 10), nginx does the same job.
const API_TARGET = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: API_TARGET },
      "/health": { target: API_TARGET },
      "/ready": { target: API_TARGET },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    exclude: [...configDefaults.exclude, "e2e/**"], // Playwright tests run separately
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
