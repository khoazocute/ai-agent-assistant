# Bước 12 — Telegram + memory
- Ngày: 2026-11-14 · Git tag: `step-12`

## Đã làm
- `harness/context/memory.py`: `conversations`, `conversation_messages` (ngắn hạn), `user_facts` (dài hạn).
- `harness/evaluation/feedback.py`: phản hồi 👍/👎 theo `run_id` (online eval).
- `agents/memory_tools.py`: `remember_fact`, `recall_facts` (cho supervisor + single).
- `app/chat.py` — `ChatService`: kiểm tra kill switch → memory → agent → lưu lượt → yêu cầu duyệt mới; lỗi model → câu báo lịch sự.
- `integrations/telegram_bot.py`: allowlist `chat_id` (fail closed, báo chat_id cho người lạ), `/start /help /reset /approvals /trace`, nút ✅ Duyệt / ❌ Từ chối, 👍/👎, chống xử lý trùng update, giới hạn độ dài, markdown → HTML an toàn.
- Tổng 141 test (không cần mạng).

## Khái niệm cần nắm
1. **Logic tách khỏi kênh**: Telegram chỉ hiển thị; `ChatService` test được bằng LLM giả. Web (bước 13) dùng lại y nguyên.
2. **Memory có trần**: N lượt chữ gần nhất → chi phí mỗi tin không tăng mãi.
3. **Fail closed**: danh sách chat_id trống = không ai dùng được.
4. **Duyệt bằng nút bấm** → gọi `Runtime.approve` → thực thi đúng tham số đã lưu (ADR-0010).
5. **Online eval**: 👎 + run_id = ca eval mới có sẵn trace.

## Câu hỏi tự kiểm tra
1. Vì sao memory không lưu kết quả tool cũ (vd. nội dung email)?
2. Vì sao agent chạy trong `asyncio.to_thread` thay vì gọi thẳng trong handler?
3. Người lạ nhắn bot thì chuyện gì xảy ra?

## Bài tập
README → "Kết nối Telegram": tạo bot, chạy `python -m app.integrations.telegram_bot`, nhắn "trưa ăn phở 45k" rồi "à nhầm, 50k".

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
