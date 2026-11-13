"""Context Harness — quyết định những gì đi vào cửa sổ ngữ cảnh của agent.

- prompts.py  load_prompt: nạp prompt.md (frontmatter + nội dung), version = hash nội dung (bước 4;
              bước 6: PromptRegistry lưu DB, chỉ kích hoạt khi eval đạt ngưỡng)
- skills.py   SkillLoader + tool load_skill (progressive disclosure)           (sau bước 5)
- memory.py   lịch sử hội thoại (ngắn hạn) + user_memory (dài hạn)             (bước 12)
- builder.py  ghép system + tools + memory + ngày giờ; giữ prompt cache ổn định (bước 12)
"""
