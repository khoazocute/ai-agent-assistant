# experiments/ — script học tập, chạy độc lập
Nơi thử nghiệm nhỏ trước khi đưa vào kiến trúc chính:
- `step01_first_tool_call.py` — gọi Gemini với 1 tool, viết tay 2 lượt, in từng message (bước 1)
- `step02_react_loop.py` — vòng ReAct + tracer, câu hỏi nhiều bước (bước 2)
- `step03_tool_registry.py` — schema sinh tự động, executor chặn tham số sai và tool rủi ro cao (bước 3)
- `demo_tools.py` — tool demo dùng chung cho các script trên
- `telegram_hello.py` — thử bot Telegram bằng long polling (bước 12)

Script ở đây được phép dùng `app/`, nhưng `app/` **không bao giờ** import từ `experiments/`.
