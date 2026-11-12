"""Context Harness — quyết định những gì đi vào cửa sổ ngữ cảnh của agent.

- prompts.py  PromptRegistry: nạp prompt.md, version = hash nội dung           (bước 6)
- skills.py   SkillLoader + tool load_skill (progressive disclosure)           (bước 4)
- memory.py   lịch sử hội thoại (ngắn hạn) + user_memory (dài hạn)             (bước 12)
- builder.py  ghép system + tools + memory + ngày giờ; giữ prompt cache ổn định (bước 12)
"""
