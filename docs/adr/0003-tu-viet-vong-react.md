# ADR-0003: Tự viết vòng ReAct, `llm_client` trung lập provider, trace JSONL
- Trạng thái: Accepted
- Ngày: 2026-11-13
- Bước: 2

## Bối cảnh
Bước 1 viết tay đúng 2 lượt gọi. Agent thật cần **lặp**: model có thể gọi 0…n tool, nhiều tool một lúc, tool có thể lỗi. Dự án cần (1) thấy chính xác prompt + tool mỗi bước, (2) sau này chèn policy/duyệt **giữa** "model đề nghị" và "tool chạy" (bước 11), (3) đổi được provider LLM (ADR-0002).

## Các phương án
**Ai điều khiển vòng lặp**
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Tự viết vòng lặp (~60 dòng) | Thấy và kiểm soát từng bước; chèn trace/policy/duyệt dễ | Tự viết, tự test |
| B. Automatic function calling của SDK Gemini | Ngắn nhất | Giấu vòng lặp; không chặn được trước khi tool chạy; gắn chặt Gemini |
| C. LangGraph / LangChain | Nhiều tính năng sẵn (checkpoint, graph) | Thêm lớp trừu tượng + phụ thuộc lớn; khó thấy cơ chế — trái mục tiêu học |

**Giao diện LLM**: (a) dùng thẳng kiểu của SDK Gemini trong vòng lặp; (b) kiểu trung lập riêng (`ToolSpec`, `ToolCall`, `ToolResult`, `LLMResponse`, `Usage`) + adapter mỗi provider.

**Nơi lưu trace ở bước này**: (a) chỉ in console; (b) file JSONL mỗi run; (c) DB ngay.

## Quyết định
- Vòng lặp: **A** — `harness/orchestration/react_loop.py`, có `max_steps` (mặc định 6).
- LLM: **(b)** — `harness/orchestration/llm_client.py` có `LLMClient` (Protocol) + `GeminiClient`. Lịch sử hội thoại là message gốc của provider, vòng lặp coi như hộp đen → không làm mất thought signature.
- Trace: **(b)** — `harness/agentops/tracer.py`, mỗi run một file `backend/data/traces/<run_id>.jsonl` + in console theo ngôn ngữ ReAct. Bước 6 thêm DB, giữ nguyên giao diện `tracer.event(...)`.
- Lỗi tool (exception, tool không tồn tại, sai tham số) **là Observation** (`is_error=True`) chứ không làm sập run.

## Hệ quả
- Được: test vòng lặp bằng `FakeLLM` không tốn tiền (`tests/test_react_loop.py`); thêm Claude chỉ cần một adapter; mỗi bước có chỗ chèn policy.
- Mất: tự lo những thứ framework có sẵn (checkpoint/resume, chạy song song tool) — làm khi thật sự cần.
- `llm_request` ghi toàn bộ history mỗi bước → file trace lớn dần theo bình phương số bước; chấp nhận được với `max_steps` nhỏ, xem lại ở bước 6.
- Xem lại khi: cần workflow nhiều nhánh/chạy dài có checkpoint → cân nhắc LangGraph (thí nghiệm so sánh sau bước 9).

## Bằng chứng
- Run thật 2026-11-13: câu hỏi "còn bao nhiêu ngày đến Tết Dương lịch 2027, tiết kiệm 85k/ngày" → 4 bước `get_current_time → days_between → calculate → trả lời`, tổng ~11,9 s, 3.502 token vào.
- Ca lỗi: `calculate("1500000 / 0")` → Observation `ZeroDivisionError`, model giải thích cho người dùng, run kết thúc `ok`.
