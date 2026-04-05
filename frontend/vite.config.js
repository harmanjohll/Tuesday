import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  server: {
    proxy: {
      "/chat": "http://localhost:8000",
      "/voice": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/reload-knowledge": "http://localhost:8000",
      "/sessions": "http://localhost:8000",
      "/agents": "http://localhost:8000",
      "/documents": "http://localhost:8000",
      "/briefing": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
