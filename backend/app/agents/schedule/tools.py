"""Tool của Schedule Agent — lớp mỏng bọc ScheduleService (ADR-0004)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated, Literal, TypeVar

from pydantic import Field

from app.config import now_vn
from app.db.models import TaskStatus
from app.db.session import SessionFactory, session_scope
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool
from app.services.schedule_service import CreatedEvent, EventOut, PlanOut, ScheduleService, SlotOut, TaskOut

T = TypeVar("T")

DateTimeArg = Annotated[datetime, Field(description="Giờ Việt Nam, dạng YYYY-MM-DDTHH:MM")]
StartDate = Annotated[date, Field(description="Ngày bắt đầu YYYY-MM-DD")]
EndDate = Annotated[date, Field(description="Ngày kết thúc YYYY-MM-DD (tính cả ngày này)")]


def build_schedule_tools(session_factory: SessionFactory, now: Callable[[], datetime] = now_vn) -> ToolRegistry:
    def with_service(fn: Callable[[ScheduleService], T]) -> T:
        with session_scope(session_factory) as s:
            return fn(ScheduleService(s, now))

    @agent_tool(risk=Risk.WRITE)
    def create_event(
        title: Annotated[str, Field(min_length=1, max_length=200, description="Tên sự kiện, vd. 'Họp nhóm'")],
        start_at: DateTimeArg,
        duration_min: Annotated[int | None, Field(gt=0, le=1440, description="Thời lượng (phút)")] = None,
        end_at: Annotated[datetime | None, Field(description="Giờ kết thúc; dùng thay cho duration_min")] = None,
        location: Annotated[str, Field(max_length=200)] = "",
        note: Annotated[str, Field(max_length=1000)] = "",
    ) -> CreatedEvent:
        """Tạo sự kiện có GIỜ CỐ ĐỊNH (họp, hẹn, lớp học). Cần duration_min hoặc end_at.
        Kết quả có `conflicts` nếu trùng giờ với sự kiện khác — hãy báo cho người dùng."""
        return with_service(lambda s: s.create_event(title, start_at, end_at, duration_min, location, note))

    @agent_tool(risk=Risk.READ)
    def list_events(start: StartDate, end: EndDate) -> list[EventOut]:
        """Liệt kê sự kiện trong khoảng ngày (có id — dùng để sửa/xoá)."""
        return with_service(lambda s: s.list_events(start, end))

    @agent_tool(risk=Risk.WRITE)
    def update_event(
        event_id: int,
        title: str | None = None,
        start_at: Annotated[datetime | None, Field(description="Giờ bắt đầu mới; thời lượng giữ nguyên")] = None,
        end_at: datetime | None = None,
        location: str | None = None,
        note: str | None = None,
    ) -> CreatedEvent:
        """Sửa hoặc dời một sự kiện (lấy id từ list_events). Chỉ truyền trường cần đổi."""
        return with_service(lambda s: s.update_event(event_id, title, start_at, end_at, location, note))

    def describe_delete(event_id: int) -> str:
        from app.db.models import Event

        with session_scope(session_factory) as s:
            e = s.get(Event, event_id)
            if e is None:
                return f"Xoá sự kiện #{event_id} (không còn tồn tại)"
            return f"Xoá sự kiện #{e.id}: {e.title} · {e.start_at:%H:%M %d/%m/%Y}–{e.end_at:%H:%M}"

    @agent_tool(risk=Risk.DESTRUCTIVE, describe=describe_delete)
    def delete_event(event_id: int) -> EventOut:
        """Xoá một sự kiện. Cần người dùng duyệt nên có thể chưa thực hiện ngay."""
        return with_service(lambda s: s.delete_event(event_id))

    @agent_tool(risk=Risk.READ)
    def find_free_slots(
        start: StartDate,
        end: EndDate,
        min_duration_min: Annotated[int, Field(ge=15, le=600, description="Chỉ lấy khung dài ít nhất")] = 30,
    ) -> list[SlotOut]:
        """Tìm khung giờ trống (07:00–22:00, đã chừa 10 phút đệm quanh sự kiện, không tính quá khứ)."""
        return with_service(lambda s: s.find_free_slots(start, end, min_duration_min))

    @agent_tool(risk=Risk.WRITE)
    def add_task(
        title: Annotated[str, Field(min_length=1, max_length=200)],
        duration_min: Annotated[int, Field(gt=0, le=600, description="Cần bao nhiêu phút")],
        deadline: Annotated[datetime | None, Field(description="Hạn chót (giờ VN), nếu có")] = None,
        priority: Annotated[Literal[1, 2, 3], Field(description="1 cao · 2 thường · 3 thấp")] = 2,
    ) -> TaskOut:
        """Thêm việc cần làm CHƯA có giờ cố định (học bài, viết báo cáo…) để planner xếp sau."""
        return with_service(lambda s: s.add_task(title, duration_min, deadline, priority))

    @agent_tool(risk=Risk.READ)
    def list_tasks(status: Literal["todo", "scheduled", "done"] | None = None) -> list[TaskOut]:
        """Liệt kê việc cần làm (mặc định: tất cả)."""
        return with_service(lambda s: s.list_tasks(TaskStatus(status) if status else None))

    @agent_tool(risk=Risk.WRITE)
    def suggest_schedule(
        start: StartDate,
        end: EndDate,
        task_ids: Annotated[list[int] | None, Field(description="Chỉ xếp các việc này; bỏ trống = mọi việc todo")]
        = None,
    ) -> PlanOut:
        """Đề xuất phương án xếp các việc todo vào giờ trống (thuật toán, không tạo sự kiện).
        Trình bày phương án cho người dùng; CHỈ apply_schedule khi người dùng đồng ý."""
        return with_service(lambda s: s.suggest_schedule(start, end, task_ids))

    @agent_tool(risk=Risk.WRITE)
    def apply_schedule(plan_id: Annotated[int, Field(description="id từ suggest_schedule")]) -> list[EventOut]:
        """Áp dụng phương án đã được người dùng đồng ý: tạo đúng các sự kiện trong phương án."""
        return with_service(lambda s: s.apply_schedule(plan_id))

    @agent_tool(risk=Risk.WRITE)
    def complete_task(task_id: int) -> TaskOut:
        """Đánh dấu một việc đã xong."""
        return with_service(lambda s: s.complete_task(task_id))

    return ToolRegistry([create_event, list_events, update_event, delete_event, find_free_slots, add_task,
                         list_tasks, suggest_schedule, apply_schedule, complete_task])
