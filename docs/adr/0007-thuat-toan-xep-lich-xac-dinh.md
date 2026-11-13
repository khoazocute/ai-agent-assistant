# ADR-0007: Thuật toán xếp lịch xác định thay vì để LLM xếp
- Trạng thái: Accepted
- Ngày: 2026-11-13
- Bước: 7

## Bối cảnh
"Chiều mai xếp 2 tiếng học tiếng Anh, trước thứ Sáu viết xong báo cáo" cần: biết hết lịch đã có, không chồng giờ, nằm trong giờ sinh hoạt, chừa khoảng nghỉ, kịp deadline. Đây là bài toán ràng buộc.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Đưa toàn bộ lịch cho LLM, để nó xếp | Linh hoạt, ít code | Hay quên một ràng buộc (chồng giờ, quá 22h); không kiểm thử được; tốn token khi lịch dài |
| B. Thuật toán tham lam xác định (`services/planner.py`) + LLM chỉ hiểu yêu cầu và giải thích | Đúng 100% theo luật, test được, cùng đầu vào cùng kết quả | Ít "tinh tế" hơn (không tự hiểu "tôi thích học buổi sáng") |
| C. Solver tối ưu (OR-Tools) | Lời giải tối ưu toàn cục | Phụ thuộc lớn; quá mức cho vài việc/ngày |

## Quyết định
Chọn **B**. `free_slots` (giờ sinh hoạt 07:00–22:00 trừ sự kiện ± 10 phút đệm) và `plan_tasks` (deadline sớm → ưu tiên cao → dài trước, đặt vào khung sớm nhất vừa). Xếp lịch là **hai bước**: `suggest_schedule` lưu `SchedulePlan` (đề xuất), `apply_schedule(plan_id)` tạo đúng các sự kiện đó sau khi người dùng đồng ý; apply kiểm tra lại trùng giờ (lịch có thể đã đổi).

## Hệ quả
- Được: 10 test planner + 12 test service; LLM không thể tạo lịch chồng giờ "âm thầm".
- Mất: sở thích mềm (học buổi sáng) chưa có — sẽ thành `PlannerRules`/skill `schedule-planning-rules` khi cần.
- Xem lại khi: số việc lớn hoặc cần tối ưu toàn cục → C.
