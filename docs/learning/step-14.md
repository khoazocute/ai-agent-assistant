# Bước 14 — Trace UI, AgentOps dashboard, realtime (SSE)
- Ngày: 2026-11-14 · Git tag: `step-14` (cùng commit với bước 13 — frontend làm liền một mạch)

## Đã làm
- Trang **Agent Runs** và **chi tiết run**: system prompt, danh sách tool, tin nhắn kèm thời điểm, timeline Thought → Action → Observation, run con của sub-agent. Đây là câu trả lời trực quan cho yêu cầu gốc "biết chính xác prompt và tool agent dùng".
- Trang **AgentOps**: theo agent (run, thành công, p50/p95, token, bước, chi phí), 👍/👎, policy hiện hành, audit gần đây.
- `app/realtime.py`: EventBus + listener `after_commit` → `GET /api/stream` (SSE) → `frontend/src/live.ts` làm mới đúng phần dữ liệu.
- `TELEGRAM_MODE=polling`: bot chạy trong tiến trình web.
- Smoke test với uvicorn thật: đăng nhập → thêm giao dịch → SSE nhận `{"topic": "finance"}`. Tổng 151 test.

## Khái niệm cần nắm
1. **Observability cho người**: trace trong DB chỉ có giá trị khi dễ đọc — timeline ReAct + link từ mỗi câu trả lời chat.
2. **Bắt thay đổi ở tầng dữ liệu** (after_commit) thay vì nhớ gọi publish ở từng chỗ.
3. **SSE vs WebSocket** (ADR-0016): chọn công cụ vừa đủ cho nhu cầu một chiều.

## Câu hỏi tự kiểm tra
1. Vì sao rollback không được phát sự kiện?
2. Bus trong tiến trình gặp vấn đề gì khi chạy 2 tiến trình web? Cách sửa?

## Bài tập
Mở trang Chi tiêu trên máy tính, nhắn Telegram "cà phê 29k" → xem trang tự cập nhật.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
