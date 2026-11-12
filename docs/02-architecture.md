# 02 — Kiến trúc
> Viết ở **bước 2–9**. Hiện là khung — nội dung đầy đủ xem `PLAN.md`.

## Nội dung dự kiến
- Sơ đồ tổng thể (Telegram/Web → FastAPI → Supervisor → agents → services → DB)
- 7 harness và ranh giới phụ thuộc
- Luồng một yêu cầu: ReAct loop, agent-as-tool, trace
- Luồng duyệt (PendingAction) và luồng realtime (SSE)
