# Bước 2 — Vòng ReAct + tracer
- Ngày: 2026-11-13 · Git tag: `step-02`

## Đã làm
- `harness/orchestration/llm_client.py`: kiểu dữ liệu trung lập (`ToolSpec`, `ToolCall`, `ToolResult`, `LLMResponse`, `Usage`) + `GeminiClient` — nơi duy nhất biết về SDK Gemini.
- `harness/orchestration/react_loop.py`: `run_react(...)` lặp tới khi model không gọi tool nữa hoặc chạm `max_steps`; lỗi tool thành Observation.
- `harness/agentops/tracer.py`: mỗi run một file `backend/data/traces/<run_id>.jsonl` + in console Thought/Action/Observation.
- `tests/test_react_loop.py`: 7 test với `FakeLLM` (không gọi mạng).
- `experiments/react_loop_demo.py`: 3 tool (`get_current_time`, `days_between`, `calculate` an toàn không dùng `eval`).

## Kết quả chạy thật
```
── Bước 1 · 2979 ms   [ACTION] get_current_time({})          [OBSERVATION] Friday 13/11/2026 21:42
── Bước 2 · 2854 ms   [ACTION] days_between(2026-11-13 → 2027-01-01)        [OBSERVATION] 49
── Bước 3 · 2089 ms   [ACTION] calculate("49 * 85000")        [OBSERVATION] 4165000
── Bước 4 · 3942 ms   [ANSWER] Hôm nay 13/11/2026 · còn 49 ngày · tiết kiệm được 4.165.000đ
■ OK sau 4 bước · tổng tokens in=3502 out=156 thinking=544
```
Ca lỗi: `calculate("1500000 / 0")` → `❌ ZeroDivisionError` → model giải thích cho người dùng, run vẫn `ok`.

## Khái niệm cần nắm
1. **Điều kiện dừng của ReAct:** model không đề nghị Action nào ⇒ câu trả lời cuối. Thêm "phanh khẩn cấp" `max_steps` để chống lặp vô hạn và tốn tiền vô hạn — quyết định dừng nằm ở **code**, không ở model.
2. **Lỗi là Observation.** Exception, tool không tồn tại, sai tham số đều được gửi lại cho model (`is_error=True`) để nó tự sửa hoặc giải thích, thay vì làm sập run.
3. **Model tự lên kế hoạch nhiều bước.** Không ai viết "gọi A rồi B rồi C" — model suy ra thứ tự từ mô tả tool và Observation trước đó. Vì vậy mô tả tool (vd. "chỉ nhận số thuần, không nhận 85k") có tác dụng như prompt.
4. **Chi phí tăng theo số bước.** Token vào: 316 → 745 → 1116 → 1325 vì mỗi bước gửi lại toàn bộ lịch sử. Tổng ≈ bình phương số bước — lý do sau này cần quản lý context và giới hạn bước.
5. **Adapter pattern cho LLM.** Vòng lặp chỉ biết `LLMClient`; Gemini chỉ là một cài đặt. Nhờ vậy test được bằng `FakeLLM` và sau này benchmark được nhiều provider.
6. **Tool không bao giờ tin input của model.** `calculate` dùng `ast` thay vì `eval()`: model (hoặc nội dung độc hại trong email mà model đọc) có thể gửi code bất kỳ.

## Quyết định (ADR liên quan)
- [ADR-0003](../adr/0003-tu-viet-vong-react.md): tự viết vòng ReAct, `llm_client` trung lập provider, trace JSONL.

## Câu hỏi tự kiểm tra
1. Nếu bỏ `max_steps`, điều gì có thể xảy ra khi một tool luôn trả lỗi? Ai trả tiền cho việc đó?
2. Vì sao vòng lặp phải nối `resp.message` vào history **trước** khi nối kết quả tool?
3. Test với `FakeLLM` chứng minh được điều gì, và **không** chứng minh được điều gì? (gợi ý: test vs eval)

## Bài tập
1. Chạy `react_loop_demo.py` với `max_steps=2` cho câu hỏi mặc định và xem `run_end` báo gì.
2. Mở file `.jsonl` mới nhất trong `backend/data/traces/`, tìm sự kiện `llm_request` của bước 3 và đếm xem history có bao nhiêu message — khớp với khái niệm 4 không?
3. (Thêm) Xoá câu "Chỉ chấp nhận số thuần (85000, không phải 85k)" khỏi mô tả `calculate`, hỏi lại và xem model có gửi "85k" rồi tự sửa sau Observation lỗi không.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
