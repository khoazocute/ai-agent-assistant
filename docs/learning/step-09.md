# Bước 9 — Multi-agent (Supervisor) + benchmark
- Ngày: 2026-11-13 · Git tag: `step-09`

## Đã làm
- `agents/supervisor/`: prompt điều phối + 2 tool `ask_finance_agent`, `ask_schedule_agent` (agent-as-tool).
  - Sub-agent chạy vòng ReAct riêng; trace là run con (`parent_run_id`) → `python -m app.cli run <id>` hiện link run con.
  - Token/tool call của sub-agent được cộng vào kết quả Supervisor (benchmark công bằng).
  - Độ sâu ủy quyền = 1 (sub-agent không có tool `ask_*`).
- `benchmarks/run.py` + `report.py`: chạy cùng bộ ca cho single vs supervisor, sinh bảng vào README (không điền tay).
- ADR-0008 (Proposed — chờ số liệu). Tổng 94 test.

## Khái niệm cần nắm
1. **Agent-as-tool**: với Supervisor, một sub-agent chỉ là một tool có input là câu yêu cầu, output là câu trả lời.
2. **Ngữ cảnh bị cô lập**: sub-agent chỉ thấy câu được giao → Supervisor phải viết câu giao việc *tự đủ ý*. Đây vừa là điểm mạnh (ít token, không lộ dữ liệu thừa) vừa là rủi ro (mất ý).
3. **Đo trước, quyết sau**: thêm agent = thêm độ trễ + token. Chỉ đáng khi chất lượng/an toàn tốt hơn — benchmark trả lời, không phải cảm giác.
4. **Chi phí thật của multi-agent** = Supervisor + mọi sub-agent.

## Câu hỏi tự kiểm tra
1. Ca "ăn phở 45k, chiều mai họp" cần bao nhiêu lượt gọi LLM ở single và ở supervisor?
2. Vì sao sub-agent không được có tool `ask_*`?
3. Theo ADR-0008, nếu single đạt 90% còn supervisor 92% nhưng chậm gấp đôi, chọn cái nào?

## Bài tập
Khi có quota/billing: `python -m benchmarks.run --suite mixed --delay 5` rồi đọc bảng ở README mục 5.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
