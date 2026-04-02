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
    },
  },
});
