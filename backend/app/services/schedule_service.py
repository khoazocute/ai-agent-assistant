"""Nghiệp vụ lịch: sự kiện, việc cần làm, tìm giờ trống, đề xuất + áp dụng phương án xếp lịch.

Đề xuất (suggest) và áp dụng (apply) là HAI bước: phương án được lưu thành SchedulePlan để người dùng
xem trước; apply tạo sự kiện ĐÚNG như đã xem (không gọi lại LLM, không tính lại) — "cái được duyệt
chính là cái được thực hiện".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import VN_TZ, now_vn
from app.db.models import CalendarTombstone, Event, SchedulePlan, Task, TaskStatus
from app.services.planner import DEFAULT_RULES, PlannerRules, Slot, TaskIn, free_slots, plan_tasks


class ScheduleError(ValueError):
    """Lỗi nghiệp vụ — thông điệp viết cho người (và model) đọc để sửa."""


def to_local(dt: datetime) -> datetime:
    """Quy mọi thời điểm về giờ VN không kèm múi giờ (cách lưu trong DB)."""
    return dt.astimezone(VN_TZ).replace(tzinfo=None) if dt.tzinfo else dt


class EventOut(BaseModel):
    id: int
    title: str
    start_at: datetime
    end_at: datetime
    location: str
    note: str
    source: str

    @classmethod
    def of(cls, e: Event) -> EventOut:
        return cls(id=e.id, title=e.title, start_at=e.start_at, end_at=e.end_at, location=e.location,
                   note=e.note, source=e.source)


class CreatedEvent(BaseModel):
    event: EventOut
    conflicts: list[EventOut]  # vẫn tạo, nhưng báo trùng giờ để agent nói cho người dùng


class TaskOut(BaseModel):
    id: int
    title: str
    duration_min: int
    deadline: datetime | None
    priority: int
    status: TaskStatus
    event_id: int | None

    @classmethod
    def of(cls, t: Task) -> TaskOut:
        return cls(id=t.id, title=t.title, duration_min=t.duration_min, deadline=t.deadline,
                   priority=t.priority, status=t.status, event_id=t.event_id)


class SlotOut(BaseModel):
    start: datetime
    end: datetime
    minutes: int


class PlanItem(BaseModel):
    task_id: int
    title: str
    start: datetime
    end: datetime


class PlanOut(BaseModel):
    plan_id: int
    status: str
    items: list[PlanItem]
    unscheduled: list[dict]


class ScheduleService:
    def __init__(self, session: Session, now: Callable[[], datetime] = now_vn,
                 rules: PlannerRules = DEFAULT_RULES) -> None:
        self.s = session
        self.now = lambda: to_local(now())
        self.rules = rules

    # ---------- Sự kiện ----------

    def create_event(self, title: str, start_at: datetime, end_at: datetime | None = None,
                     duration_min: int | None = None, location: str = "", note: str = "") -> CreatedEvent:
        start_at = to_local(start_at)
        if end_at is None:
            if not duration_min:
                raise ScheduleError("Cần end_at hoặc duration_min.")
            end_at = start_at + timedelta(minutes=duration_min)
        end_at = to_local(end_at)
        self._validate_range(start_at, end_at)
        conflicts = self._overlapping(start_at, end_at)
        e = Event(title=title.strip(), start_at=start_at, end_at=end_at, location=location, note=note)
        self.s.add(e)
        self.s.flush()
        return CreatedEvent(event=EventOut.of(e), conflicts=[EventOut.of(c) for c in conflicts])

    def list_events(self, start: date, end: date) -> list[EventOut]:
        lo, hi = datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)
        q = select(Event).where(Event.end_at > lo, Event.start_at < hi).order_by(Event.start_at)
        return [EventOut.of(e) for e in self.s.scalars(q)]

    def update_event(self, event_id: int, title: str | None = None, start_at: datetime | None = None,
                     end_at: datetime | None = None, location: str | None = None,
                     note: str | None = None) -> CreatedEvent:
        e = self._get_event(event_id)
        new_start = to_local(start_at) if start_at else e.start_at
        # Dời giờ bắt đầu mà không nói giờ kết thúc → giữ nguyên thời lượng.
        new_end = to_local(end_at) if end_at else new_start + (e.end_at - e.start_at)
        self._validate_range(new_start, new_end)
        if new_start != e.start_at:
            e.reminded_at = None  # dời giờ → nhắc lại theo giờ mới
        e.start_at, e.end_at = new_start, new_end
        if title is not None:
            e.title = title.strip()
        if location is not None:
            e.location = location
        if note is not None:
            e.note = note
        e.synced_at = None  # đánh dấu "có thay đổi local" → lần đồng bộ Google sau sẽ đẩy lên
        self.s.flush()
        conflicts = [c for c in self._overlapping(new_start, new_end) if c.id != e.id]
        return CreatedEvent(event=EventOut.of(e), conflicts=[EventOut.of(c) for c in conflicts])

    def delete_event(self, event_id: int) -> EventOut:
        e = self._get_event(event_id)
        out = EventOut.of(e)
        for t in self.s.scalars(select(Task).where(Task.event_id == e.id)):
            t.event_id, t.status = None, TaskStatus.TODO  # việc đã xếp vào sự kiện này quay lại "chưa xếp"
        if e.gcal_event_id:  # đã có trên Google → nhớ để lần đồng bộ sau xoá bên đó (bước 15)
            self.s.merge(CalendarTombstone(gcal_event_id=e.gcal_event_id))
        self.s.delete(e)
        return out

    # ---------- Giờ trống ----------

    def find_free_slots(self, start: date, end: date, min_duration_min: int = 30) -> list[SlotOut]:
        slots = self._free_slots(start, end)
        return [SlotOut(start=s.start, end=s.end, minutes=s.minutes) for s in slots if s.minutes >= min_duration_min]

    def _free_slots(self, start: date, end: date) -> list[Slot]:
        if end < start:
            raise ScheduleError(f"Ngày kết thúc {end} trước ngày bắt đầu {start}.")
        window_start = max(datetime.combine(start, time.min), self.now())  # không xếp vào quá khứ
        window_end = datetime.combine(end, time.max)
        busy = [(e.start_at, e.end_at) for e in self.s.scalars(
            select(Event).where(Event.end_at > window_start, Event.start_at < window_end))]
        return free_slots(busy, window_start, window_end, self.rules)

    # ---------- Việc cần làm + xếp lịch ----------

    def add_task(self, title: str, duration_min: int, deadline: datetime | None = None, priority: int = 2) -> TaskOut:
        if duration_min <= 0:
            raise ScheduleError("Thời lượng phải > 0 phút.")
        if not 1 <= priority <= 3:
            raise ScheduleError("priority: 1 (cao), 2 (thường), 3 (thấp).")
        t = Task(title=title.strip(), duration_min=duration_min,
                 deadline=to_local(deadline) if deadline else None, priority=priority)
        self.s.add(t)
        self.s.flush()
        return TaskOut.of(t)

    def list_tasks(self, status: TaskStatus | None = None) -> list[TaskOut]:
        q = select(Task).order_by(Task.deadline.is_(None), Task.deadline, Task.priority, Task.id)
        if status:
            q = q.where(Task.status == status)
        return [TaskOut.of(t) for t in self.s.scalars(q)]

    def complete_task(self, task_id: int) -> TaskOut:
        t = self.s.get(Task, task_id)
        if t is None:
            raise ScheduleError(f"Không có việc #{task_id}.")
        t.status = TaskStatus.DONE
        return TaskOut.of(t)

    def suggest_schedule(self, start: date, end: date, task_ids: list[int] | None = None) -> PlanOut:
        q = select(Task).where(Task.status == TaskStatus.TODO)
        if task_ids:
            q = q.where(Task.id.in_(task_ids))
        tasks = list(self.s.scalars(q))
        if not tasks:
            raise ScheduleError("Không có việc nào đang chờ xếp lịch. Hãy add_task trước.")
        result = plan_tasks(
            [TaskIn(t.id, t.title, t.duration_min, t.deadline, t.priority) for t in tasks],
            self._free_slots(start, end), self.rules,
        )
        plan = SchedulePlan(
            items=[{"task_id": p.task_id, "title": p.title, "start": p.start.isoformat(), "end": p.end.isoformat()}
                   for p in result.placements],
            unscheduled=[{"task_id": i, "title": title, "reason": r} for i, title, r in result.unscheduled],
        )
        self.s.add(plan)
        self.s.flush()
        return self._plan_out(plan)

    def apply_schedule(self, plan_id: int) -> list[EventOut]:
        plan = self.s.get(SchedulePlan, plan_id)
        if plan is None:
            raise ScheduleError(f"Không có kế hoạch #{plan_id}.")
        if plan.status != "proposed":
            raise ScheduleError(f"Kế hoạch #{plan_id} đã ở trạng thái '{plan.status}', không áp dụng lại được.")
        items = [PlanItem.model_validate(i) for i in plan.items]
        # Lịch có thể đã thay đổi kể từ lúc đề xuất → kiểm tra lại, không tạo chồng giờ một cách âm thầm.
        clashes = [i.title for i in items if self._overlapping(i.start, i.end)]
        if clashes:
            raise ScheduleError(f"Lịch đã thay đổi, trùng giờ với: {', '.join(clashes)}. Hãy đề xuất lại.")
        created = []
        for item in items:
            e = Event(title=item.title, start_at=item.start, end_at=item.end, note=f"Xếp từ kế hoạch #{plan_id}")
            self.s.add(e)
            self.s.flush()
            task = self.s.get(Task, item.task_id)
            if task is not None:
                task.status, task.event_id = TaskStatus.SCHEDULED, e.id
            created.append(EventOut.of(e))
        plan.status = "applied"
        return created

    # ---------- Nội bộ ----------

    def _plan_out(self, plan: SchedulePlan) -> PlanOut:
        return PlanOut(plan_id=plan.id, status=plan.status, items=[PlanItem.model_validate(i) for i in plan.items],
                       unscheduled=plan.unscheduled)

    def _get_event(self, event_id: int) -> Event:
        e = self.s.get(Event, event_id)
        if e is None:
            raise ScheduleError(f"Không có sự kiện #{event_id}.")
        return e

    def _validate_range(self, start: datetime, end: datetime) -> None:
        if end <= start:
            raise ScheduleError("Giờ kết thúc phải sau giờ bắt đầu.")
        if end - start > timedelta(days=1):
            raise ScheduleError("Một sự kiện không dài quá 24 giờ — có nhầm ngày không?")

    def _overlapping(self, start: datetime, end: datetime) -> list[Event]:
        q = select(Event).where(Event.start_at < end, Event.end_at > start).order_by(Event.start_at)
        return list(self.s.scalars(q))
