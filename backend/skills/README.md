# skills/ — runtime skills cho agent
Mỗi skill là một thư mục chứa `SKILL.md` (frontmatter `name`, `description` + hướng dẫn chi tiết).
Agent ban đầu chỉ thấy **tên + mô tả** (rất ít token); gọi tool `load_skill(name)` để nạp nội dung khi cần — gọi là *progressive disclosure*.

| Skill | Agent | Bước |
|---|---|---|
| `vn-money-parsing` | Finance | 4 |
| `expense-categorization` | Finance | 4 |
| `schedule-planning-rules` | Schedule | 7 |
| `email-triage` | Email | 10 |
| `email-reply-style` | Email | 11 |
| `receipt-reading` | Finance (ảnh hóa đơn) | 17 |
