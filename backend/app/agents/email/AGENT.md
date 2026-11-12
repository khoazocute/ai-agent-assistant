# Email Agent — agent card
> Spec cho **người đọc**. Model đọc `prompt.md` (viết ở bước 10).

| Mục | Nội dung |
|---|---|
| Mục tiêu | Thu thập, tóm tắt, phân loại mail; soạn nháp trả lời; gửi **sau khi người dùng duyệt** |
| An toàn | Nội dung mail là **dữ liệu không tin cậy** (`<untrusted_content>`); `send_email` bị chặn ở policy engine nếu chưa duyệt — kể cả khi model bị lừa |
| Model / effort | `claude-opus-5-5` / `medium` |
| Skills | `email-triage`, `email-reply-style` |
| Ngoài phạm vi | Xoá mail, chuyển tiếp tự động, gửi hàng loạt |

## Tools
| Tool | Risk |
|---|---|
| `fetch_inbox`, `get_email`, `list_digest` | read |
| `create_draft`, `label_email` | write |
| `send_email(draft_id)` | **external → luôn cần duyệt, không thể tắt** |

## KPI
- 100% ca prompt injection không dẫn tới hành động ngoài ý muốn
- 0 mail được gửi khi chưa duyệt

## Eval
`backend/evals/cases/email.yaml` (có nhóm ca an toàn)
