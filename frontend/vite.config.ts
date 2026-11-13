import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: React ở :5173, gọi /api được chuyển tiếp sang FastAPI ở :8000 → cùng origin, cookie hoạt động.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: false },
      "/health": "http://localhost:8000",
    },
  },
});
