"""Planner — thuật toán thuần, phải đúng 100%: không chồng giờ, trong giờ sinh hoạt, kịp deadline."""

from datetime import datetime as dt

from app.services.planner import PlannerRules, Slot, TaskIn, free_slots, plan_tasks

D = dt(2026, 11, 14)  # Thứ Bảy


def at(h: int, m: int = 0, day: int = 14) -> dt:
    return dt(2026, 11, day, h, m)


def spans(slots):
    return [(s.start.strftime("%d %H:%M"), s.end.strftime("%d %H:%M")) for s in slots]


def test_empty_day_is_one_slot_within_waking_hours():
    assert spans(free_slots([], at(0), at(23, 59))) == [("14 07:00", "14 22:00")]


def test_events_are_subtracted_with_buffer():
    busy = [(at(9), at(10)), (at(14), at(15, 30))]
    assert spans(free_slots(busy, at(0), at(23, 59))) == [
        ("14 07:00", "14 08:50"), ("14 10:10", "14 13:50"), ("14 15:40", "14 22:00")]


def test_overlapping_events_are_merged_and_short_gaps_dropped():
    busy = [(at(9), at(10)), (at(9, 30), at(11)), (at(11, 20), at(12))]  # khe 11:10–11:10 sau đệm → bỏ
    assert spans(free_slots(busy, at(0), at(23, 59))) == [("14 07:00", "14 08:50"), ("14 12:10", "14 22:00")]


def test_window_start_cuts_the_past_and_spans_multiple_days():
    slots = free_slots([], at(20), at(23, 59, day=15))
    assert spans(slots) == [("14 20:00", "14 22:00"), ("15 07:00", "15 22:00")]


def test_event_crossing_midnight():
    busy = [(at(21), at(8, day=15))]
    assert spans(free_slots(busy, at(0), at(23, 59, day=15))) == [("14 07:00", "14 20:50"), ("15 08:10", "15 22:00")]


def test_plan_places_earliest_deadline_first_without_overlap():
    slots = [Slot(at(7), at(9)), Slot(at(14), at(18))]
    tasks = [TaskIn(1, "Đọc sách", 60, priority=3),
             TaskIn(2, "Báo cáo", 90, deadline=at(12)),
             TaskIn(3, "Tiếng Anh", 120, priority=1)]
    r = plan_tasks(tasks, slots)
    placed = {p.task_id: (p.start.strftime("%H:%M"), p.end.strftime("%H:%M")) for p in r.placements}
    assert placed == {2: ("07:00", "08:30"), 3: ("14:00", "16:00"), 1: ("16:10", "17:10")}
    assert r.unscheduled == []
    ordered = sorted(r.placements, key=lambda p: p.start)
    assert all(a.end <= b.start for a, b in zip(ordered, ordered[1:], strict=False))


def test_task_that_cannot_meet_deadline_is_reported_not_forced():
    r = plan_tasks([TaskIn(1, "Gấp", 120, deadline=at(8))], [Slot(at(7), at(9))])
    assert r.placements == [] and r.unscheduled == [(1, "Gấp", "không kịp trước deadline")]


def test_task_longer_than_any_slot():
    r = plan_tasks([TaskIn(1, "Dài", 300)], [Slot(at(7), at(9))])
    assert r.unscheduled == [(1, "Dài", "không còn khung trống đủ dài")]


def test_deterministic():
    tasks = [TaskIn(i, f"t{i}", 30) for i in range(5)]
    slots = [Slot(at(7), at(12))]
    assert plan_tasks(tasks, slots).placements == plan_tasks(list(reversed(tasks)), slots).placements


def test_custom_rules():
    rules = PlannerRules(buffer_min=0)
    assert spans(free_slots([(at(9), at(10))], at(0), at(23, 59), rules))[0] == ("14 07:00", "14 09:00")
