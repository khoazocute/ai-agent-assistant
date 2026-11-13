# experiments/ — script học tập, chạy độc lập
Nơi thử nghiệm nhỏ trước khi đưa vào kiến trúc chính:
- `step01_first_tool_call.py` — gọi Gemini với 1 tool, viết tay 2 lượt, in từng message (bước 1)
- `step02_react_loop.py` — vòng ReAct + tracer với 3 tool, câu hỏi nhiều bước (bước 2)
- `telegram_hello.py` — thử bot Telegram bằng long polling (bước 12)

Script ở đây được phép dùng `app/`, nhưng `app/` **không bao giờ** import từ `experiments/`.
