# Bước 16 — Bản tin sáng/tối + job nền
- Ngày: 2026-11-14 · Git tag: `step-16`

## Đã làm
- `services/briefing_service.py`: gom số liệu bằng code (lịch, việc sắp hạn, chi tiêu, thư mới + cờ đáng ngờ, chờ duyệt) + `fallback_text`.
- `agents/briefing/`: `prompt.md` + `workflow.py` (1 lượt LLM, 0 tool, có trace) — ADR-0014.
- `app/notify.py`: Telegram/log, giờ yên lặng 22:30–06:30, markdown → HTML an toàn.
- `app/jobs/scheduler.py` (APScheduler trong event loop của web): bản tin 07:00/21:00, nhắc sự kiện trước 15 phút (mỗi sự kiện một lần, dời giờ thì nhắc lại), đồng bộ Google 10 phút, kéo mail 15 phút (báo thư đáng ngờ), dọn trace > 90 ngày lúc 03:00; job lỗi được cô lập + audit.
- CLI `python -m app.cli brief morning|evening [--send]`. Tổng 163 test.

## Kết quả chạy thật
`python -m app.cli brief morning` → Gemini viết bản tin từ JSON do code tính (lịch trống, chi 0đ…): đúng số liệu, 1 request.

## Khái niệm cần nắm
1. **Agent vs workflow** (ADR-0014): đường đi cố định → workflow rẻ và chắc hơn.
2. **Luôn có đường lui**: LLM lỗi → mẫu dựng sẵn; người dùng vẫn nhận bản tin.
3. **Tin chủ động phải lịch sự**: giờ yên lặng, không nhắc lặp.
4. **Job nền cô lập lỗi**: một job hỏng không kéo cả scheduler.
5. **Lưu trữ có hạn**: trace chứa dữ liệu cá nhân → xoá sau 90 ngày.

## Câu hỏi tự kiểm tra
1. Vì sao đánh dấu `reminded_at` TRƯỚC khi gửi tin nhắc?
2. Vì sao nội dung thư không được đưa vào prompt bản tin?

## Bài tập
Thêm vào bản tin sáng "ngân sách còn lại tháng này" khi bạn đặt một mức ngân sách (gợi ý: thêm vào `BriefData` + test).

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
