# Briefing — agent card
> Đây là **workflow** (1 lần gọi LLM), không phải vòng ReAct — xem ADR-0014 (bước 16).

| Mục | Nội dung |
|---|---|
| Mục tiêu | Bản tin 7h sáng và tổng kết 21h tối gửi qua Telegram |
| Luồng | `BriefingService.collect()` lấy số liệu bằng code (không LLM) → 1 lần gọi LLM viết bản tin → gửi Telegram + lưu `briefings` |
| Bản tin sáng | Lịch hôm nay, việc cần làm, mail quan trọng, ngân sách còn lại |
| Tổng kết tối | Tổng chi hôm nay, hỏi khoản chưa ghi, việc chưa xong (nút Xong / Dời sang mai / Bỏ) |
| Governance | Giờ yên lặng 22:30–06:30, giới hạn số tin chủ động mỗi ngày |
| Model / effort | `claude-opus-5-5` / `low` |

## KPI
- Số liệu trong bản tin khớp 100% với DB (vì do code tính)
- Bản tin gửi đúng giờ, không gửi trong giờ yên lặng
