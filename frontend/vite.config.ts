import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into ../web/dist and served by FastAPI. `npm run dev` proxies the API to a local server on :8000.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "../web/dist", emptyOutDir: true, assetsDir: "assets", sourcemap: false },
  server: {
    proxy: Object.fromEntries(["/api", "/config.js", "/health", "/jobs", "/ops"].map((p) => [p, "http://localhost:8000"])),
  },
});
