# Bước 7 — Schedule Agent + planner
- Ngày: 2026-11-13 · Git tag: `step-07`

## Đã làm
- Bảng `events`, `tasks`, `schedule_plans` (giờ VN không kèm múi giờ).
- `services/planner.py`: `free_slots`, `plan_tasks` — hàm thuần, xác định (ADR-0007).
- `services/schedule_service.py`: tạo/sửa/xoá/xem sự kiện (báo trùng giờ), việc cần làm, `suggest_schedule` → `apply_schedule`.
- `agents/schedule/`: `prompt.md`, `tools.py` (10 tool), `agent.py`.
- `agents/base.py`: `BaseAgent` dùng chung (chèn thời điểm, version prompt, hàm tạo executor); `agents/registry.py`.
- Vòng ReAct nhận `history` (các lượt trước) — chuẩn bị cho memory ở bước 12.
- CLI: `chat --agent schedule`, `events`. 22 test mới (tổng 87).

## Khái niệm cần nắm
1. **Giao cho code việc có luật, giao cho LLM việc ngôn ngữ.** LLM: "chiều mai 3h" → `2026-11-14T15:00`. Code: tìm giờ trống, xếp việc.
2. **Đề xuất ≠ thực hiện.** `suggest_schedule` lưu phương án; `apply_schedule` tạo đúng phương án đó — người dùng duyệt cái sẽ xảy ra.
3. **Kiểm tra lại lúc thực hiện** (apply phát hiện lịch đã đổi) — nguyên tắc tương tự sẽ dùng cho duyệt email ở bước 11.
4. **Thuật toán xác định** → test được bằng số liệu chính xác (07:00–08:30, 14:00–16:00…).

## Câu hỏi tự kiểm tra
1. Vì sao `apply_schedule` không gọi lại planner mà dùng đúng các mục đã lưu?
2. Khoảng đệm 10 phút được áp vào đâu: sự kiện, hay khung trống?
3. Nếu LLM tự trả lời "bạn rảnh 9h–11h" mà không gọi `find_free_slots`, rủi ro là gì? Prompt chặn việc này thế nào?

## Bài tập
1. Thêm luật "không xếp việc trong giờ ăn trưa 11:30–13:00" vào `PlannerRules` + test.
2. `python -m app.cli chat --agent schedule`: "mai cần 2 tiếng học tiếng Anh và 1 tiếng viết báo cáo, xếp giúp tôi" → đồng ý kế hoạch → `python -m app.cli events`.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
