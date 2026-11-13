# ADR-0013: Lịch lưu trong DB của app + đồng bộ hai chiều Google Calendar
- Trạng thái: Accepted
- Ngày: 2026-11-14
- Bước: 15

## Bối cảnh
Người dùng xem lịch trên điện thoại bằng Google Calendar, nhưng planner (ADR-0007), eval và web cần lịch trong DB của app (truy vấn nhanh, test được, không phụ thuộc mạng).

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Chỉ dùng Google Calendar (không lưu DB) | Một nguồn | Mọi thao tác/eval cần mạng + OAuth; planner chậm; khó test |
| B. Chỉ DB của app | Đơn giản | Không thấy lịch trên điện thoại, không thấy lịch người khác mời |
| C. **DB là nguồn làm việc + đồng bộ hai chiều** | Nhanh, test được, vẫn thấy trên điện thoại | Phải xử lý xung đột, xoá, token hết hạn |

## Quyết định
**C** — `services/calendar_sync.py`, mỗi lượt: **đẩy** (mới → insert, sửa → patch, xoá → tombstone → delete) rồi **kéo** (syncToken tăng dần; 410 → đồng bộ lại toàn bộ).
- Tín hiệu "cần đẩy" là `synced_at = NULL` (ScheduleService đặt khi sửa) — **không** so `updated_at > synced_at` (bài học: so thời gian + `onupdate` tự đặt giờ → đẩy ngược, ghi đè lệnh xoá từ Google).
- Bỏ qua bản thay đổi có `etag` trùng (chính mình vừa đẩy). Xung đột: đẩy trước → **local thắng** (đơn giản, dễ đoán).
- Sự kiện cả ngày bị bỏ qua (planner cần giờ cụ thể). Giờ quy về giờ VN.
- Chạy: `python -m app.cli gcal-sync`, nút trên trang Lịch, job nền mỗi 10 phút (bước 16).
- Schema: thêm cột mới cho DB đã có bằng `add_missing_columns` (chỉ cột cho phép rỗng); migration đầy đủ ở bước 20.

## Hệ quả
- Không có webhook đẩy từ Google → thay đổi trên điện thoại vào app sau ≤ 10 phút.
- Sửa cùng lúc ở hai nơi → bản trên Google bị ghi đè bởi bản local (chấp nhận với một người dùng).
