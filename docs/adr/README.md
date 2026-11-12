# Architecture Decision Records
Mẫu: [0000-template.md](0000-template.md). Quy trình: [ADR-0001](0001-dung-adr.md).

| ADR | Quyết định | Bước | Trạng thái |
|---|---|---|---|
| [0001](0001-dung-adr.md) | Ghi lại quyết định kiến trúc bằng ADR | 0 | Accepted |
| 0002 | Chọn Claude Opus 5.5 + Anthropic SDK | 1 | Dự kiến |
| 0003 | Tự viết vòng ReAct thay vì Tool Runner / LangChain / LangGraph | 2 | Dự kiến |
| 0004 | Tool là lớp mỏng bọc service | 4 | Dự kiến |
| 0005 | Phát triển theo eval, ngưỡng release prompt | 5 | Dự kiến |
| 0006 | Tự lưu trace vào DB thay vì Langfuse/LangSmith | 6 | Dự kiến |
| 0007 | Thuật toán xếp lịch xác định thay vì để LLM xếp | 7 | Dự kiến |
| 0008 | Single-agent hay multi-agent — theo số liệu benchmark | 9 | Dự kiến |
| 0009 | Email là dữ liệu không tin cậy; lớp chống prompt injection | 10 | Dự kiến |
| 0010 | Sau khi duyệt, thực thi xác định — không gọi lại LLM | 11 | Dự kiến |
| 0011 | Chiến lược memory & context | 12 | Dự kiến |
| 0012 | FastAPI + React; SQLite khi học, PostgreSQL khi chạy thật | 13 | Dự kiến |
| 0013 | Lịch lưu DB + đồng bộ Google Calendar | 15 | Dự kiến |
| 0014 | Workflow thay cho agent cho bản tin và đọc hóa đơn | 16 | Dự kiến |
| 0015 | Speech-to-text local bằng faster-whisper | 18 | Dự kiến |
| — | SSE cho cập nhật realtime (thay vì WebSocket/polling) | 14 | Dự kiến |
