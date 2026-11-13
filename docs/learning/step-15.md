# Bước 15 — Đồng bộ Google Calendar
- Ngày: 2026-11-14 · Git tag: `step-15`

## Đã làm
- `integrations/calendar_provider.py` (giao diện + `FakeCalendarProvider` mô phỏng syncToken/etag), `integrations/gcal_client.py` (Calendar API v3).
- `services/calendar_sync.py`: đẩy (mới/sửa/xoá qua tombstone) → kéo (syncToken, 410 → đồng bộ lại).
- Bảng `calendar_tombstones`, `sync_state`; cột `events.synced_at`; `add_missing_columns` (thêm cột mới cho DB cũ).
- `python -m app.cli gcal-sync`, `POST /api/schedule/sync-google`, nút trên trang Lịch. Tổng 155 test.

## Khái niệm cần nắm
1. **Đồng bộ tăng dần** bằng syncToken; token hết hạn → đồng bộ lại toàn bộ, không nhân đôi.
2. **Tombstone**: xoá ở local phải "nhớ" để xoá ở xa — nếu không, lần kéo sau sự kiện sống lại.
3. **Tín hiệu tường minh > so thời gian**: lỗi thật đã gặp — so `updated_at > synced_at` làm đẩy ngược ghi đè lệnh xoá.
4. **Tiến hoá schema an toàn**: thêm cột cho phép rỗng thì tự động được; đổi/xoá cột cần migration.

## Câu hỏi tự kiểm tra
1. Nếu bỏ bảng tombstone, xoá một sự kiện ở web rồi đồng bộ thì chuyện gì xảy ra?
2. Vì sao bỏ qua thay đổi có `etag` trùng?

## Bài tập
Kết nối Google (README), tạo sự kiện trên điện thoại, chạy `python -m app.cli gcal-sync`, kiểm tra trang Lịch.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
