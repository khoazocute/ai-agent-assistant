# Architecture Decision Records
Mẫu: [0000-template.md](0000-template.md). Quy trình: [ADR-0001](0001-dung-adr.md).

| ADR | Quyết định | Bước | Trạng thái |
|---|---|---|---|
| [0001](0001-dung-adr.md) | Ghi lại quyết định kiến trúc bằng ADR | 0 | Accepted |
| [0002](0002-chon-llm-gemini.md) | Dùng Google Gemini qua SDK `google-genai` (đổi từ Claude) | 1 | Accepted |
| [0003](0003-tu-viet-vong-react.md) | Tự viết vòng ReAct (không AFC / LangGraph), `llm_client` trung lập provider, trace JSONL | 2 | Accepted |
| [0004](0004-tool-la-lop-mong-boc-service.md) | Tool là lớp mỏng bọc service; con số do code tính | 4 | Accepted |
| [0005](0005-phat-trien-theo-eval.md) | Phát triển theo eval; chấm bằng code; ngưỡng 90% + an toàn 100% | 5 | Accepted |
| [0006](0006-tu-luu-trace-vao-db.md) | Tự lưu trace vào DB thay vì Langfuse/LangSmith | 6 | Accepted |
| [0007](0007-thuat-toan-xep-lich-xac-dinh.md) | Thuật toán xếp lịch xác định thay vì để LLM xếp | 7 | Accepted |
| [0008](0008-single-hay-multi-agent.md) | Single-agent hay multi-agent — theo số liệu benchmark | 9 | Proposed |
| [0009](0009-email-la-du-lieu-khong-tin-cay.md) | Email là dữ liệu không tin cậy; chống prompt injection nhiều lớp | 10 | Accepted |
| [0010](0010-thuc-thi-xac-dinh-sau-khi-duyet.md) | Policy-as-code + duyệt; sau khi duyệt thực thi xác định, không gọi lại LLM | 11 | Accepted |
| [0011](0011-chien-luoc-memory-context.md) | Chiến lược memory & context: 6 lượt chữ gần nhất + facts tra khi cần | 12 | Accepted |
| [0012](0012-fastapi-react-sqlite.md) | FastAPI + React cùng domain; SQLite khi học, PostgreSQL khi chạy thật | 13 | Accepted |
| [0013](0013-lich-db-dong-bo-google-calendar.md) | Lịch lưu DB + đồng bộ hai chiều Google Calendar | 15 | Accepted |
| [0014](0014-workflow-cho-ban-tin-va-hoa-don.md) | Workflow thay cho agent cho bản tin và đọc hóa đơn | 16 | Accepted |
| 0015 | Speech-to-text local bằng faster-whisper | 18 | Dự kiến |
| [0016](0016-sse-cap-nhat-realtime.md) | SSE cho cập nhật realtime (thay vì WebSocket/polling) | 14 | Accepted |
