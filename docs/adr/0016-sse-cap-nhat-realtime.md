# ADR-0016: Server-Sent Events cho cập nhật realtime (thay vì WebSocket/polling)
- Trạng thái: Accepted
- Ngày: 2026-11-14
- Bước: 14

## Bối cảnh
Nhắn Telegram "ăn phở 45k" → trang Chi tiêu đang mở phải cập nhật ngay, không cần F5. Dữ liệu có thể đổi từ nhiều nơi: tool của agent, web, duyệt, job nền.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Polling mỗi N giây | Đơn giản | Trễ N giây; tốn request khi không có gì đổi |
| B. WebSocket | Hai chiều | Thừa (chỉ cần server → trình duyệt); cần quản lý kết nối/giao thức riêng |
| C. **SSE** (`text/event-stream`) | HTTP thường, một chiều đúng nhu cầu, trình duyệt tự kết nối lại, đi qua proxy dễ | Chỉ một chiều (đủ dùng) |

**Phát sự kiện từ đâu**: gọi `publish` trong từng service, hay bắt ở tầng DB?

## Quyết định
- **C**. `GET /api/stream` (cần đăng nhập) phát `{"topic": "finance"|"schedule"|"email"|"approvals"|"runs"}`; giao diện chỉ làm mới các truy vấn của chủ đề đó (TanStack Query).
- Phát sự kiện bằng **listener SQLAlchemy `after_commit`** trên session factory: mọi đường ghi đều được bắt, không thể quên; rollback không phát gì. Mỗi commit một sự kiện mỗi chủ đề.
- Bus trong tiến trình (`app/realtime.py`), an toàn khi gọi từ thread (agent chạy trong threadpool); hàng đợi mỗi trình duyệt có giới hạn (bỏ tin cũ khi trình duyệt chậm); comment keepalive mỗi 15 giây.
- `TELEGRAM_MODE=polling`: bot chạy **chung tiến trình** với web để bus thấy được thay đổi do Telegram ghi.

## Hệ quả
- Chỉ hoạt động trong một tiến trình. Nhiều tiến trình/máy → thay bus bằng PostgreSQL `LISTEN/NOTIFY` hoặc Redis pub/sub (giữ nguyên giao diện `publish/subscribe`).
