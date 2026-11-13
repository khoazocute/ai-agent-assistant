"""Planner — tìm khung giờ trống và xếp việc vào đó. Hàm THUẦN: không DB, không LLM (ADR-0007).

Vì sao không để LLM tự xếp lịch: xếp lịch là bài toán ràng buộc (không chồng giờ, trước deadline,
trong giờ sinh hoạt, có khoảng đệm). Code giải đúng 100% và kiểm thử được; LLM dễ "quên" một
ràng buộc. LLM chỉ làm phần nó giỏi: hiểu "chiều mai xếp 2 tiếng học tiếng Anh" và giải thích phương án.

Thuật toán (tham lam, xác định — cùng đầu vào luôn cùng kết quả):
  1. free_slots: lấy khung giờ sinh hoạt mỗi ngày (07:00–22:00), trừ đi các sự kiện (mở rộng thêm
     khoảng đệm 10 phút hai đầu), bỏ khúc ngắn hơn 15 phút.
  2. plan_tasks: xếp việc theo thứ tự deadline sớm → ưu tiên cao → dài trước; mỗi việc đặt vào
     khung trống SỚM NHẤT đủ dài và kết thúc trước deadline. Việc không chia nhỏ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class PlannerRules:
    day_start: time = time(7, 0)
    day_end: time = time(22, 0)  # không xếp việc sau 22h
    buffer_min: int = 10  # nghỉ giữa hai việc
    min_slot_min: int = 15


DEFAULT_RULES = PlannerRules()  # frozen → dùng chung an toàn làm giá trị mặc định


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class TaskIn:
    id: int
    title: str
    duration_min: int
    deadline: datetime | None = None
    priority: int = 2


@dataclass(frozen=True)
class Placement:
    task_id: int
    title: str
    start: datetime
    end: datetime


@dataclass
class PlanResult:
    placements: list[Placement]
    unscheduled: list[tuple[int, str, str]]  # (task_id, title, lý do)


def free_slots(
    busy: list[tuple[datetime, datetime]],
    window_start: datetime,
    window_end: datetime,
    rules: PlannerRules = DEFAULT_RULES,
) -> list[Slot]:
    buffer = timedelta(minutes=rules.buffer_min)
    # Mở rộng mỗi sự kiện thêm khoảng đệm, rồi gộp các khoảng chồng nhau.
    blocked = _merge(sorted((s - buffer, e + buffer) for s, e in busy if e > window_start and s < window_end))

    slots: list[Slot] = []
    day: date = window_start.date()
    while day <= window_end.date():
        lo = max(datetime.combine(day, rules.day_start), window_start)
        hi = min(datetime.combine(day, rules.day_end), window_end)
        cursor = lo
        for b_start, b_end in blocked:
            if b_end <= cursor or b_start >= hi:
                continue
            if b_start > cursor:
                slots.append(Slot(cursor, min(b_start, hi)))
            cursor = max(cursor, b_end)
        if cursor < hi:
            slots.append(Slot(cursor, hi))
        day += timedelta(days=1)
    return [s for s in slots if s.minutes >= rules.min_slot_min]


def plan_tasks(tasks: list[TaskIn], slots: list[Slot], rules: PlannerRules = DEFAULT_RULES) -> PlanResult:
    far_future = datetime.max
    order = sorted(tasks, key=lambda t: (t.deadline or far_future, t.priority, -t.duration_min, t.id))
    remaining = sorted(slots, key=lambda s: s.start)
    buffer = timedelta(minutes=rules.buffer_min)
    placements: list[Placement] = []
    unscheduled: list[tuple[int, str, str]] = []

    for task in order:
        need = timedelta(minutes=task.duration_min)
        chosen = None
        for i, slot in enumerate(remaining):
            end = slot.start + need
            if end > slot.end:
                continue
            if task.deadline and end > task.deadline:
                break  # các khung sau còn muộn hơn → không thể kịp deadline
            chosen = i
            break
        if chosen is None:
            reason = "không kịp trước deadline" if task.deadline else "không còn khung trống đủ dài"
            unscheduled.append((task.id, task.title, reason))
            continue
        slot = remaining.pop(chosen)
        end = slot.start + need
        placements.append(Placement(task.id, task.title, slot.start, end))
        rest = Slot(end + buffer, slot.end)  # phần còn lại của khung, sau khoảng đệm
        if rest.minutes >= rules.min_slot_min:
            remaining.insert(chosen, rest)

    placements.sort(key=lambda p: p.start)
    return PlanResult(placements, unscheduled)


def _merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged
