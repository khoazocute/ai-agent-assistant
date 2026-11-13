# ADR-0014: Workflow (không phải agent) cho bản tin và đọc hóa đơn
- Trạng thái: Accepted
- Ngày: 2026-11-14
- Bước: 16 (áp dụng lại ở bước 17)

## Bối cảnh
Bản tin 7h/21h và đọc ảnh hóa đơn có các bước **biết trước**: lấy dữ liệu → viết/trích xuất → gửi/đề xuất. Có nên dùng agent ReAct (model tự quyết gọi tool nào) cho chúng?

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Agent ReAct với tool đọc chi tiêu, lịch, mail | Linh hoạt | 4–6 lượt gọi LLM; có thể quên một mục, tính sai số; khó đoán chi phí |
| B. **Workflow**: code gom dữ liệu → 1 lượt LLM (không tool) viết lời → gửi; LLM lỗi → mẫu dựng sẵn | 1 lượt gọi; số liệu luôn đúng (do code); luôn gửi được | Ít linh hoạt (cần sửa code để thêm mục) |

## Quyết định
**B**. Quy tắc chung: *dùng agent khi đường đi phụ thuộc vào yêu cầu; dùng workflow khi đường đi cố định.*
- `services/briefing_service.py` tính mọi con số; nội dung thư (không tin cậy) **không** đưa vào prompt — chỉ người gửi, tiêu đề, cờ đáng ngờ.
- `agents/briefing/workflow.py`: `run_react` với 0 tool, `max_steps=1` → vẫn có trace + chi phí như mọi run.
- Fallback `fallback_text` khi LLM lỗi/hết quota/không có key.
- Tin chủ động tôn trọng giờ yên lặng 22:30–06:30 (`app/notify.py`).

## Hệ quả
- Bản tin tốn đúng 1 request/lần (quan trọng với quota 20 request/ngày).
- Thêm mục mới vào bản tin = sửa code + test, không chỉ sửa prompt.
