# Briefing — agent card
> Đây là **workflow** (1 lần gọi LLM), không phải vòng ReAct — xem ADR-0014 (bước 16).

| Mục | Nội dung |
|---|---|
| Mục tiêu | Bản tin 7h sáng và tổng kết 21h tối gửi qua Telegram |
| Luồng | `BriefingService.collect()` lấy số liệu bằng code (không LLM) → 1 lần gọi LLM viết bản tin ([workflow.py](workflow.py)) → gửi Telegram; LLM lỗi → `fallback_text`; trace như mọi run |
| Bản tin sáng | Lịch hôm nay, việc cần làm, mail quan trọng, ngân sách còn lại |
| Tổng kết tối | Tổng chi hôm nay, hỏi khoản chưa ghi, việc chưa xong (nút Xong / Dời sang mai / Bỏ) |
| Governance | Giờ yên lặng 22:30–06:30 ([notify.py](../../notify.py)); nội dung thư không đưa vào prompt |
| Model | `GEMINI_MODEL` — ADR-0002 |

## KPI
- Số liệu trong bản tin khớp 100% với DB (vì do code tính)
- Bản tin gửi đúng giờ, không gửi trong giờ yên lặng
