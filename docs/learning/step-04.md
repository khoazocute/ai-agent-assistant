# Bước 4 — Finance Agent đầu tiên: DB + service + tools + CLI
- Ngày: 2026-11-13 · Git tag: `step-04`

## Đã làm
| File | Vai trò |
|---|---|
| `app/config.py` | Đọc `.env` một chỗ (pydantic-settings); `now_vn()`, `today_vn()` |
| `app/db/models.py`, `app/db/session.py` | Bảng `categories`, `transactions` (SQLAlchemy 2); `session_scope` = một transaction |
| `app/services/finance_service.py` | Nghiệp vụ: thêm/liệt kê/xoá, `get_summary` (chi, thu, **chi ròng**, %), `resolve_period` |
| `app/agents/finance/tools.py` | 4 tool mỏng: `add_transaction` (write), `get_summary`, `list_transactions` (read), `delete_transaction` (destructive) |
| `app/agents/finance/prompt.md` | System prompt: danh mục, cách đọc "45k / 1tr5 / 1 lít", khi nào dùng tool nào |
| `app/agents/finance/agent.py` | Ghép prompt + tool + vòng ReAct; chèn thời điểm hiện tại vào user message |
| `app/harness/context/prompts.py` | Nạp `prompt.md`, version = hash nội dung (ghi vào trace) |
| `app/cli.py` | `python -m app.cli chat / summary / list` |
| `tests/` | +27 test: service (không LLM), tools, agent với `FakeLLM`; tổng 47 |

Thêm: experiments đổi tên theo nội dung (`react_loop_demo.py`…); khi LLM lỗi, trace vẫn ghi `run_end status=error`.

## Kết quả chạy thật
```
Bạn: trưa nay ăn phở 45k, đổ xăng 60k, tối qua đi xem phim 120k
  [ACTION] add_transaction({"amount_vnd": 45000, "category": "an_uong", "note": "ăn phở"})
  [ACTION] add_transaction({"amount_vnd": 60000, "category": "di_chuyen", "note": "đổ xăng"})
  [ACTION] add_transaction({"amount_vnd": 120000, "category": "giai_tri", "occurred_on": "2026-11-12", "note": "xem phim"})
  [ANSWER] Đã ghi 3 khoản: Ăn phở 45.000đ (Ăn uống) · Đổ xăng 60.000đ (Di chuyển) · Xem phim 120.000đ (Giải trí, hôm qua 12/11)

Bạn: tháng này tôi chi bao nhiêu rồi?
  [ACTION] get_summary({"period": "this_month"})
  [OBSERVATION] {total_expense_vnd: 225000, net_spending_vnd: 225000, by_category: [giai_tri 53.3%, …]}

$ python -m app.cli summary          ← cùng service, KHÔNG qua LLM, cùng con số
  Tổng chi 225.000đ · Tổng thu 0đ · Chi ròng 225.000đ
```
Hai lần gọi sau gặp lỗi Gemini: `504 DEADLINE_EXCEEDED` (một lượt mất 250 s vì retry) và `429 RESOURCE_EXHAUSTED` — **gói miễn phí chỉ cho 20 request/ngày cho mỗi model**. CLI báo lỗi rồi cho nhập tiếp, không sập.

## Khái niệm cần nắm
1. **Tool mỏng, service dày (ADR-0004).** Tool chỉ mở phiên DB và gọi service. CLI `summary` gọi cùng service và ra cùng con số — một nguồn sự thật.
2. **Con số do code tính.** Model chỉ chọn `period="this_month"`; code quy ra 01/11–30/11 và cộng tiền. LLM giỏi hiểu ngôn ngữ, không đáng tin khi cộng trừ.
3. **Enum trong schema = danh sách lựa chọn cho model.** `category` là `Literal[...]` → model chỉ chọn được danh mục có thật; chọn sai bị chặn trước khi chạm DB.
4. **Phòng thủ nhiều lớp cho dữ liệu tiền:** schema (`gt=0`) → service (`FinanceError`) → DB (`CHECK amount_vnd > 0`).
5. **Thời điểm hiện tại nằm trong user message**, không trong system prompt: system prompt cố định → version ổn định, tốt cho prompt cache; thời gian thì luôn mới.
6. **Tiêm "hôm nay" (dependency injection).** Service/tool/agent nhận hàm `today()` → test cố định ngày 13/11/2026, kết quả không đổi theo ngày chạy.
7. **Hạn mức là ràng buộc thiết kế.** 20 request/ngày ≈ 7–10 câu hỏi. Bước 5 (eval) cần hàng chục lượt gọi → cần tính chuyện quota trước.

## Quyết định (ADR liên quan)
- [ADR-0004](../adr/0004-tool-la-lop-mong-boc-service.md): tool là lớp mỏng bọc service; con số do code tính.

## Câu hỏi tự kiểm tra
1. Vì sao `get_summary` nhận `period="last_month"` thay vì để model tự truyền `start/end`?
2. Nếu bỏ `Literal` của `category` (chỉ để `str`), lỗi nào có thể lọt vào DB? Lớp nào còn chặn được?
3. Vì sao test dùng DB SQLite **trong RAM** và "hôm nay" cố định, thay vì DB thật và đồng hồ thật?

## Bài tập
1. Thêm danh mục chi `suc_khoe` (thuốc, khám bệnh): sửa `CategoryKey`, `DEFAULT_CATEGORIES`, `prompt.md`; chạy pytest xem test nào bắt bạn sửa đồng bộ.
2. Thêm `period="last_7_days"` vào `resolve_period` + một test.
3. Chạy `python -m app.cli chat`, nhắn "hôm qua ăn bún 35k" rồi `python -m app.cli list` kiểm tra ngày.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
