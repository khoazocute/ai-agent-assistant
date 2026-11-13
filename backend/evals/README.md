# evals/ — bộ đánh giá agent với LLM thật
Viết eval **trước** khi tinh chỉnh prompt (ADR-0005). Test (`tests/`) chứng minh code đúng; eval đo **model** làm đúng bao nhiêu.

- `cases/finance.yaml` — 15 ca: ghi chi/thu, tiếng lóng tiền ("1 lít", "1tr2"), ngày tương đối, thiếu số tiền, báo cáo, 3 ca an toàn
- `run.py` — chạy và chấm; mỗi ca một DB mới trong RAM, "bây giờ" cố định 13/11/2026 12:30
- `media/` — ảnh hóa đơn và đoạn thu âm mẫu (bước 17–18)

```powershell
cd backend
python -m evals.run                                  # toàn bộ — dùng ~30 request
python -m evals.run --case fin-010 --case fin-013    # vài ca (lọc theo tiền tố id)
python -m evals.run --limit 5 --delay 5              # 5 ca đầu, nghỉ 5s giữa các ca
python -m evals.run --model gemini-3.5-flash-lite    # model khác (quota riêng)
```
Kết quả: `backend/data/evals/*.json` · trace từng ca: `backend/data/traces/evals/` (không commit).

**Ngưỡng release prompt:** tổng ≥ 90% **và** ca an toàn 100%. Chạy thiếu ca → không kết luận.

## Thêm một ca
```yaml
- id: fin-016-ten-ngan-gon
  input: "câu người dùng"
  setup: [{amount_vnd: 45000, category: an_uong, occurred_on: 2026-11-13}]   # tuỳ chọn
  safety: false                                                              # tuỳ chọn
  expect:
    transactions: [{amount_vnd: 45000, category: an_uong, occurred_on: today}]  # giao dịch MỚI, khớp chính xác
    must_call: [get_summary]
    must_not_call: [add_transaction]
    answer_numbers: [105000]
    answer_not_contains: ["đã xoá"]
    asks_clarification: true
```
