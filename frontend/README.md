# frontend/ — website (Vite + React + TypeScript)
TanStack Query (dữ liệu) · FullCalendar (lịch) · Recharts (biểu đồ) · SSE (`/api/stream`, realtime).

Trang: Tổng quan · Chat · Chi tiêu · Lịch · Email & Duyệt · Agent Runs (trace từng bước) · AgentOps.

```powershell
npm install
npm run dev      # http://localhost:5173 — /api được proxy sang FastAPI ở :8000
npm run build    # tạo dist/ — FastAPI tự phục vụ ở http://localhost:8000 (cùng domain)
```
