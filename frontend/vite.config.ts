import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into ../web/dist and served by FastAPI (Render runs no npm build, so web/dist is committed).
// `npm run dev` proxies the API to a local server on :8000.
export default defineConfig({
  plugins: [react()],
  base: "/",
  resolve: {
    // shadcn-style components from Vengeance UI / Skiper UI import from "@/..."
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: { outDir: "../web/dist", emptyOutDir: true, assetsDir: "assets", sourcemap: false },
  server: {
    proxy: Object.fromEntries(["/api", "/config.js", "/health", "/jobs", "/ops"].map((p) => [p, "http://localhost:8000"])),
  },
});
