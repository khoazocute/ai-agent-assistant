# Schedule Agent — agent card
> Spec cho **người đọc**. Model đọc [`prompt.md`](prompt.md). Code: [`agent.py`](agent.py), [`tools.py`](tools.py), planner: [`services/planner.py`](../../services/planner.py).

| Mục | Nội dung |
|---|---|
| Mục tiêu | Đặt lịch theo yêu cầu, tìm khung trống, gợi ý xếp việc, nhắc lịch |
| Nguyên tắc | **Code tính giờ, LLM chỉ hiểu yêu cầu và giải thích** — `planner.py` là thuật toán xác định (ADR-0007) |
| Lưu trữ | DB riêng + đồng bộ 2 chiều Google Calendar (bước 15) |
| Model | `GEMINI_MODEL` — ADR-0002 |
| Skills | `schedule-planning-rules` |
| Ngoài phạm vi | Đặt lịch hộ người khác, gửi lời mời họp (thuộc Email Agent) |

## Tools
| Tool | Risk |
|---|---|
| `create_event`, `update_event`, `apply_schedule(plan_id)`, `reschedule_task`, `sync_google_calendar` | write |
| `list_events`, `find_free_slots(from, to, duration, constraints)`, `suggest_schedule(tasks)` | read |
| `delete_event` | destructive → cần duyệt |

## KPI
- 0 lần xếp chồng lịch; 0 lần xếp vào giờ ngủ / giờ yên lặng
- ≥ 90% yêu cầu ngày giờ tiếng Việt hiểu đúng ("chiều mai", "thứ 6 tuần sau")

## Eval
`backend/evals/cases/schedule.yaml`
