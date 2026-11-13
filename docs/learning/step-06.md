# Bước 6 — Trace vào DB, chi phí, độ trễ
- Ngày: 2026-11-13 · Git tag: `step-06`

## Đã làm
- `harness/storage.py`: `HarnessBase` — bảng riêng của harness, tách khỏi bảng nghiệp vụ.
- `harness/agentops/tracer.py`: Tracer gửi sự kiện tới nhiều **sink** (JSONL, console, DB); `tracer.child()` cho sub-agent (`parent_run_id`).
- `harness/agentops/store.py`: bảng `agent_runs` + `agent_events`, `DbTraceSink`, hàm đọc lại.
- `harness/agentops/cost.py` + `config/pricing.yaml`: chi phí từ token × giá; chưa có giá → "—".
- `harness/agentops/metrics.py`: tỉ lệ thành công, p50/p95 (nearest-rank), token, bước, chi phí theo agent.
- CLI: `python -m app.cli runs`, `run <id>`, `stats`. 6 test mới (tổng 65).

## Khái niệm cần nắm
1. **Sink pattern**: vòng ReAct chỉ gọi `tracer.event()`; thêm nơi lưu = thêm sink, không sửa vòng lặp.
2. **Hai mức chi tiết**: `agent_runs` (1 dòng/run, có cột để lọc & thống kê) vs `agent_events` (mọi thứ, JSON).
3. **p95 quan trọng hơn trung bình**: trung bình 3s nhưng p95 = 55s (lúc Gemini quá tải) — người dùng nhớ lần chờ 55s.
4. **Không đoán giá**: chi phí sai còn tệ hơn không có chi phí.
5. **Dữ liệu cá nhân ở lại máy**: lý do chính không dùng dịch vụ trace bên ngoài.

## Câu hỏi tự kiểm tra
1. Vì sao `DbTraceSink` mở một phiên DB ngắn cho mỗi sự kiện thay vì một phiên cho cả run?
2. Một run có `status=running` mãi không đổi — điều đó cho biết gì?
3. Vì sao token suy nghĩ (thinking) được tính tiền như token đầu ra?

## Bài tập
1. Điền giá thật của `gemini-3.5-flash` vào `config/pricing.yaml`, chat vài câu rồi chạy `python -m app.cli stats`.
2. Chạy `python -m app.cli run <id>` cho một run và tìm đúng system prompt model đã đọc.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
