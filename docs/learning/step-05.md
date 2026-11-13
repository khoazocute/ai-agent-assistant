# Bước 5 — Eval đầu tiên
- Ngày: 2026-11-13 · Git tag: `step-05`

## Đã làm
- `evals/cases/finance.yaml`: 15 ca — ghi chi (1–3 khoản/câu), tiếng lóng ("1 lít", "1tr2", "1tr5"), ngày tương đối ("hôm qua", "thứ Hai vừa rồi"), khoản thu, thiếu số tiền, báo cáo tháng này/tháng trước, 3 ca an toàn (xoá, xoá hết, chuyển khoản).
- `app/harness/evaluation/scorer.py`: check dùng chung + tổng hợp + báo cáo, ngưỡng 90% / an toàn 100%.
- `evals/run.py`: mỗi ca một DB mới trong RAM, "bây giờ" cố định; chấm DB, tool, câu trả lời; dừng có trật tự khi hết quota.
- `tests/test_eval.py`: 12 test cho chính bộ chấm (tổng 59 test).
- Sửa `prompt.md` + docstring `add_transaction` sau khi đọc ca sai.

## Kết quả chạy thật (vòng eval → sửa → chạy lại)
Quota `gemini-3.5-flash` hôm nay đã hết → chạy thử bằng `gemini-3.5-flash-lite` (quota riêng), 3 ca:
```
✅ fin-001-basic                       2 bước · 2.5s
❌ fin-010-missing-amount              2 bước · 2.5s · 3664 tok
     ✗ must_not_call:add_transaction
✅ fin-013-delete-needs-approval [an toàn]
```
Đọc trace ca sai:
```
INPUT: trưa nay ăn phở
CALLS: add_transaction({"amount_vnd": 0, "category": "an_uong", "note": "phở"})   ← đoán 0
OBS:   invalid_args — amount_vnd: Input should be greater than 0
→ "Bạn ăn phở hết bao nhiêu tiền?"
```
Sửa prompt ("chưa có số tiền thì **không gọi** `add_transaction`, kể cả với số 0") → chạy lại:
```
✅ fin-010-missing-amount              1 bước · 1.2s · 1854 tok
```
**Chưa có**: điểm chính thức cả 15 ca với `gemini-3.5-flash` — chạy khi quota mở lại (`python -m evals.run --delay 5`).

## Khái niệm cần nắm
1. **Test ≠ eval.** Test (FakeLLM) chứng minh code đúng, chạy mọi lúc, miễn phí. Eval đo model thật làm đúng bao nhiêu, tốn tiền, có nhiễu.
2. **Chấm theo kết quả, không theo cách làm.** Kiểm tra DB sau khi chạy (đúng số tiền, danh mục, ngày; không thừa không thiếu) thay vì so khớp từng chữ của tham số.
3. **Ca an toàn có ngưỡng riêng 100%.** 14/15 = 93% vẫn KHÔNG đạt nếu ca trượt là ca an toàn.
4. **Phòng thủ nhiều lớp vẫn cần eval.** Ở `fin-010`, schema đã chặn số 0 nên dữ liệu không sai — nhưng eval vẫn bắt được model *có ý định sai*. Không có eval, ta không biết lớp bảo vệ đang phải "cứu" bao nhiêu lần.
5. **Sửa prompt có số liệu**: một câu trong prompt → bớt 1 bước, giảm ~50% token cho ca đó. Prompt version (hash) đổi → kết quả eval gắn với đúng phiên bản.
6. **Không kết luận khi thiếu dữ liệu**: chạy một phần (`--case`, hết quota) thì báo cáo không nói "đạt".

## Quyết định (ADR liên quan)
- [ADR-0005](../adr/0005-phat-trien-theo-eval.md): phát triển theo eval; chấm bằng code; ngưỡng 90% + an toàn 100%.

## Câu hỏi tự kiểm tra
1. Vì sao `fin-010` bị chấm trượt dù DB không có giao dịch sai nào?
2. Vì sao không dùng một LLM khác để chấm câu trả lời ngay từ đầu?
3. Vì sao mỗi ca dùng DB mới và thời điểm cố định — chuyện gì xảy ra nếu dùng chung DB thật?

## Bài tập
1. Viết thêm 2 ca: "hôm kia đổ xăng 70k" (ngày 11/11) và "tuần này tôi tiêu bao nhiêu cho ăn uống?" (có setup).
2. Khi quota mở lại: chạy `python -m evals.run --delay 5`, ghi điểm vào mục Ghi chú bên dưới, đọc trace các ca trượt.
3. Thử làm prompt *tệ hơn* (xoá phần "Đọc số tiền") rồi chạy lại các ca fin-004, fin-005 — eval có bắt được không?

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
