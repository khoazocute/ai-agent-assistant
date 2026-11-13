# Bước 8 — Single-agent (một agent nắm mọi tool)
- Ngày: 2026-11-13 · Git tag: `step-08`

## Đã làm
- `agents/single/`: prompt = phần chung + prompt Finance + prompt Schedule (`compose_prompts`), 14 tool (`ToolRegistry.merge`).
- Eval tổng quát hoá: `setup` có `transactions/events/tasks`; kiểm tra `events`, `events_final`, `tasks`, `answer_contains`.
- Bộ ca mới: `schedule.yaml` (11 ca), `mixed.yaml` (5 ca liên miền). `single` chạy cả 3 bộ (31 ca, 5 ca an toàn).
- `python -m evals.run --agent single` · `chat --agent single`. Tổng 89 test.

## Khái niệm cần nắm
1. **Single-agent là đối chứng.** Trước khi thêm Supervisor (phức tạp hơn), phải biết một agent làm được tới đâu — nếu đủ tốt thì không cần multi-agent.
2. **Giới hạn của single-agent**: prompt dài (~4.800 ký tự), 14 tool — model phải chọn đúng giữa nhiều tool; mỗi lượt gửi lại toàn bộ prompt + schema → tốn token.
3. **Cùng bộ ca cho mọi cấu hình** → so sánh công bằng (bước 9).
4. **Ca liên miền** ("ăn phở 45k, chiều mai họp") là nơi hai cách tiếp cận khác nhau rõ nhất.

## Câu hỏi tự kiểm tra
1. Khi nào nên dừng ở single-agent và không làm multi-agent?
2. Vì sao version prompt của single đổi khi sửa `finance/prompt.md`?

## Bài tập
Khi có quota: `python -m evals.run --agent single --delay 5`, ghi lại tỉ lệ đạt và token trung bình.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
