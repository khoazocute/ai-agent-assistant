import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: React ở :5173, gọi /api được chuyển tiếp sang FastAPI ở :8000 → cùng origin, cookie hoạt động.
export default defineConfig({
  plugins: [react()],
  // Sourcemap cho bản build thật: khi lỗi xảy ra (như "l is not a function"), DevTools → Console
  // hiện đúng tên biến/file/dòng TypeScript gốc thay vì tên đã bị rút gọn khi minify.
  build: { sourcemap: true },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: false },
      "/health": "http://localhost:8000",
    },
  },
});
