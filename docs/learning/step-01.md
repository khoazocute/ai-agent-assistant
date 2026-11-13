# Bước 1 — Gọi LLM lần đầu với một tool
- Ngày: 2026-11-13 · Git tag: `step-01`

## Đã làm
- Đổi LLM từ Claude sang **Google Gemini** (`gemini-3.5-flash`, SDK `google-genai`) vì chưa có Anthropic key → [ADR-0002](../adr/0002-chon-llm-gemini.md).
- Viết `backend/experiments/first_tool_call.py`: **hai lượt gọi viết tay** (không vòng lặp) với một tool `get_current_time`, in từng phần Thought / Action / Observation / Text và lưu toàn bộ request/response vào `backend/data/traces/first_tool_call.json` (không commit).
- Thêm timeout 45s + retry có backoff cho lỗi tạm thời (429/500/503/504).

## Kết quả chạy thật
```
=== Lượt 1 · finish_reason=STOP · tokens in=122 out=25 thinking=83
  [THOUGHT]     …there's a get_current_time function… I'll call it with "Asia/Ho_Chi_Minh"
  [ACTION]      get_current_time({"timezone": "Asia/Ho_Chi_Minh"})
  [OBSERVATION] Friday 13/11/2026 13:25:47 (UTC+0700)
=== Lượt 2 · finish_reason=STOP · tokens in=417 out=102 thinking=457
  [THOUGHT]     …13:25:47 is past 12 PM, so the target is noon TOMORROW… 22h34m13s…
  [TEXT]        Bây giờ là 13:25:47… còn 22 giờ 34 phút 13 giây đến 12 giờ trưa ngày mai.
```
Đối chứng: hỏi cùng câu nhưng **không có tool**, model bịa ra "14:52, thứ Năm, ngày 23".

## Khái niệm cần nắm
1. **Tool use = model *đề nghị*, code *thực thi*.** Model chỉ thấy tên + mô tả + schema của tool, không thấy code. Nó trả về `function_call`; chính chương trình của mình chạy hàm rồi gửi `function_response` lại. → Mọi quyền kiểm soát (duyệt, chặn, trace) nằm ở phía code — nền móng của Tool Harness và Governance Harness.
2. **Description của tool là một phần của prompt.** Viết rõ "làm gì" và "khi nào dùng" quyết định model có gọi đúng tool hay không.
3. **API không có trạng thái (stateless).** Mỗi lượt phải gửi lại toàn bộ lịch sử → token lượt 2 (417) > lượt 1 (122). Đây là lý do sau này cần quản lý context (Context Harness).
4. **Gửi lại nguyên vẹn nội dung model trả** (`candidates[0].content`, có *thought signature*) — không tự dựng lại.
5. **Thought là bản tóm tắt suy luận**, không phải chuỗi suy nghĩ thô; đủ để trace và debug.
6. **Gọi mạng luôn cần timeout + retry**, nhưng chỉ retry lỗi tạm thời (5xx, 429), không retry lỗi do yêu cầu sai (400, 404).

## Quyết định (ADR liên quan)
- [ADR-0002](../adr/0002-chon-llm-gemini.md): dùng Gemini qua `google-genai`; bước 2 sẽ có `llm_client` trung lập provider.

## Câu hỏi tự kiểm tra
1. Ở lượt 2, vì sao phải gửi lại cả câu hỏi ban đầu và nội dung lượt 1, thay vì chỉ gửi kết quả tool?
2. Gemini báo `finish_reason=STOP` ở cả hai lượt. Code biết lượt 1 là "muốn gọi tool" bằng cách nào?
3. Vì sao lỗi 503 nên thử lại, còn 404 (sai tên model) thì không?

## Bài tập
Thêm tool thứ hai `get_weekday_vn` (trả về thứ trong tuần bằng tiếng Việt), đổi câu hỏi thành "Hôm nay thứ mấy?" và quan sát model chọn tool nào. Mở `backend/data/traces/first_tool_call.json` để xem chính xác những gì đã gửi đi.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
