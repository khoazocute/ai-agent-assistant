# ADR-0012: FastAPI + React (Vite) cùng domain; SQLite khi học, PostgreSQL khi chạy thật
- Trạng thái: Accepted
- Ngày: 2026-11-14
- Bước: 13

## Bối cảnh
Cần website để quản lý dữ liệu (chi tiêu, lịch, email, duyệt) và xem trace. Backend đã là Python; agent chạy đồng bộ, mất vài giây đến vài chục giây.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. FastAPI (API) + React SPA, **cùng domain** (FastAPI phục vụ `frontend/dist`) | Một tiến trình, không cần CORS, cookie httpOnly SameSite=Lax hoạt động; React hệ sinh thái lớn (FullCalendar, Recharts) | Hai ngôn ngữ |
| B. Server-rendered (Jinja/HTMX) | Ít JS | Lịch kéo-thả, biểu đồ, cập nhật realtime khó hơn |
| C. Next.js riêng + API riêng | Mạnh | Hai server, CORS, quá mức cho một người dùng |

## Quyết định
- **A**. Router API mỏng gọi đúng các service mà agent dùng (ADR-0004) → web và agent luôn ra cùng con số.
- Đăng nhập: một chủ sở hữu, `WEB_PASSWORD` → JWT trong cookie **httpOnly**; so mật khẩu thời gian hằng; giới hạn đăng nhập sai theo IP; thiếu cấu hình → từ chối (fail closed).
- Thao tác người dùng tự bấm trên web (xoá, dời lịch) không qua duyệt nhưng **ghi audit trong cùng transaction**; luồng duyệt dành cho hành động do agent đề xuất.
- Agent chạy trong threadpool (`run_in_threadpool`) để server vẫn phục vụ request khác.
- DB: SQLite (WAL + busy_timeout) khi học/dùng một người; đổi `DATABASE_URL` sang PostgreSQL khi triển khai (bước 20).

## Hệ quả
- Bài học thật: ghi audit bằng một phiên DB thứ hai trong lúc phiên của request còn giữ khoá ghi → SQLite treo. Test dùng DB trong RAM (một kết nối) không bắt được → test API chuyển sang DB dạng file.
- Bundle JS ~950 KB (FullCalendar + Recharts) — chấp nhận cho ứng dụng cá nhân; tách code nếu cần.
