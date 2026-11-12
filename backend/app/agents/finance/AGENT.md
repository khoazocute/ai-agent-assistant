# Finance Agent — agent card
> Spec cho **người đọc**. Model đọc `prompt.md` (viết ở bước 4).

| Mục | Nội dung |
|---|---|
| Mục tiêu | Ghi và tổng hợp thu chi cá nhân chính xác |
| Đầu vào | Yêu cầu đã chắt lọc từ Supervisor (hoặc gọi trực tiếp ở chế độ single-agent) |
| Đầu ra | Câu trả lời tiếng Việt ngắn gọn + dữ liệu đã ghi vào DB |
| Danh mục chi | ăn uống, di chuyển, mua sắm, giải trí, khác |
| Danh mục thu | thu nhập, phụ cấp gia đình — trừ vào tổng chi → **chi ròng = chi − thu** |
| Model / effort | `claude-opus-5-5` / `low` |
| Skills | `vn-money-parsing`, `expense-categorization`, `receipt-reading` (bước 17) |
| Ngoài phạm vi | Tư vấn đầu tư, chuyển tiền, truy cập tài khoản ngân hàng |

## Tools
| Tool | Risk |
|---|---|
| `add_transaction(amount_vnd, category, date, note)` | write |
| `update_transaction(id, ...)`, `set_budget(category, month, amount)` | write |
| `list_transactions`, `get_summary(period)`, `get_category_breakdown`, `check_budget` | read |
| `propose_transaction(...)` — từ ảnh/giọng nói, chờ xác nhận | write (đề xuất) |
| `delete_transaction(id)` | destructive → cần duyệt |

## KPI
- ≥ 95% giao dịch đúng số tiền; ≥ 90% đúng danh mục
- 0 lần xoá mà không qua duyệt

## Eval
`backend/evals/cases/finance.yaml` (bước 5)
