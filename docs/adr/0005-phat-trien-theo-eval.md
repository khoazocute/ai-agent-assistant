# ADR-0005: Phát triển theo eval; chấm bằng code; ngưỡng 90% + an toàn 100%
- Trạng thái: Accepted
- Ngày: 2026-11-13
- Bước: 5

## Bối cảnh
Prompt và mô tả tool sẽ được sửa liên tục. Không đo thì mỗi lần sửa chỉ là "cảm thấy tốt hơn" — và sửa chỗ này có thể làm hỏng chỗ khác. Test với `FakeLLM` (bước 2–4) chỉ chứng minh **code** đúng, không chứng minh **model** hiểu đúng tiếng Việt. Ràng buộc thêm: gói Gemini miễn phí chỉ ~20 request/ngày/model.

## Các phương án
**Cách chấm**
| Phương án | Ưu | Nhược |
|---|---|---|
| A. So khớp chính xác tham số tool | Đơn giản | Quá cứng: `note: "phở"` vs `"ăn phở"` đều đúng mà bị chấm sai |
| B. So **trạng thái kết quả** (DB sau khi chạy, tool có/không được gọi, con số trong câu trả lời) | Chấm đúng thứ người dùng quan tâm; khoan dung với cách diễn đạt | Phải viết check cho từng loại kết quả |
| C. LLM chấm LLM (LLM-as-judge) | Chấm được văn phong, độ hữu ích | Tốn thêm request (quota!), không ổn định, có thiên vị |

**Ngưỡng**: một con số tổng, hay tổng + ngưỡng riêng cho ca an toàn.

## Quyết định
- Chấm theo **B**, bằng code. Check dùng chung ở `harness/evaluation/scorer.py`; check riêng agent (DB) ở `evals/run.py`.
- Ca viết bằng YAML (`evals/cases/<agent>.yaml`), kiểm tra định dạng bằng pydantic `extra="forbid"` (gõ sai tên khoá → lỗi ngay).
- Mỗi ca chạy trên **DB mới trong RAM** với **thời điểm cố định** (Thứ Sáu 13/11/2026 12:30) → độc lập, lặp lại được.
- Ngưỡng release prompt: **tổng ≥ 90% VÀ ca an toàn = 100%**. Chạy thiếu ca (hết quota, hoặc lọc `--case`) → **không kết luận**.
- Hết quota (429) → dừng có trật tự, lưu kết quả đã có; hỗ trợ `--case`, `--limit`, `--delay`, `--model`.
- Mỗi kết quả ghi `prompt_version` + `model` → so sánh được giữa các lần sửa.

## Hệ quả
- Được: vòng lặp *eval → đọc trace ca sai → sửa prompt → chạy lại* có số liệu; 10 test bảo vệ chính bộ chấm.
- Mất: check theo trạng thái không bắt được câu trả lời "đúng nhưng khó chịu" (văn phong) — để LLM-as-judge sau, khi có quota.
- Bộ 15 ca còn nhỏ: điểm 93% vs 100% chỉ khác 1 ca. Mở rộng dần từ phản hồi 👎 thật (bước 12).
- Xem lại khi: có billing (chạy nhiều lần/ngày, lấy trung bình để giảm nhiễu), hoặc cần chấm văn phong.

## Bằng chứng
Chạy thử 2026-11-13 với `gemini-3.5-flash-lite` (quota model chính đã hết): `fin-010` ("trưa nay ăn phở" — thiếu số tiền) **trượt**: model gọi `add_transaction(amount_vnd=0)`, schema chặn, rồi mới hỏi lại. Sửa prompt + docstring tool → chạy lại **đạt**, 1 bước thay vì 2, token 3664 → 1854.
