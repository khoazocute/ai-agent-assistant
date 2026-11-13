"""ScheduleService + tools + agent (LLM giả)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from conftest import NOW
from fakes import FakeLLM

from app.agents.schedule.agent import ScheduleAgent
from app.agents.schedule.tools import build_schedule_tools
from app.db.session import session_scope
from app.harness.orchestration.llm_client import ToolCall
from app.harness.tools.executor import ToolExecutor
from app.services.schedule_service import ScheduleError, ScheduleService

TOMORROW = date(2026, 11, 14)


def dt(day: int, h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, day, h, m)


@pytest.fixture
def svc(session_factory):
    with session_scope(session_factory) as s:
        yield ScheduleService(s, now=lambda: NOW)


def test_create_with_duration_and_detect_conflict(svc):
    a = svc.create_event("Họp nhóm", dt(14, 15), duration_min=60)
    assert (a.event.end_at, a.conflicts) == (dt(14, 16), [])
    b = svc.create_event("Gọi khách", dt(14, 15, 30), end_at=dt(14, 16, 30))
    assert [c.title for c in b.conflicts] == ["Họp nhóm"]


def test_timezone_aware_input_is_stored_as_vietnam_time(svc):
    utc = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)  # = 15:00 giờ VN
    assert svc.create_event("X", utc, duration_min=30).event.start_at == dt(14, 15)


@pytest.mark.parametrize(("start", "end", "message"), [
    (dt(14, 15), dt(14, 14), "sau giờ bắt đầu"),
    (dt(14, 15), dt(16, 15), "24 giờ"),
])
def test_invalid_ranges(svc, start, end, message):
    with pytest.raises(ScheduleError, match=message):
        svc.create_event("X", start, end_at=end)


def test_move_event_keeps_duration(svc):
    e = svc.create_event("Họp", dt(14, 15), duration_min=90).event
    moved = svc.update_event(e.id, start_at=dt(14, 17)).event
    assert (moved.start_at, moved.end_at) == (dt(14, 17), dt(14, 18, 30))


def test_list_events_by_day(svc):
    svc.create_event("Hôm nay", dt(13, 15), duration_min=30)
    svc.create_event("Ngày mai", dt(14, 9), duration_min=30)
    assert [e.title for e in svc.list_events(TOMORROW, TOMORROW)] == ["Ngày mai"]


def test_free_slots_never_in_the_past(svc):
    slots = svc.find_free_slots(date(2026, 11, 13), date(2026, 11, 13))
    assert slots[0].start == NOW.replace(tzinfo=None)  # hôm nay chỉ tính từ 12:30


def test_suggest_then_apply_creates_exact_events(svc):
    svc.create_event("Họp", dt(14, 7), duration_min=120)  # 07:00–09:00 bận
    t1 = svc.add_task("Học tiếng Anh", 120, priority=1)
    t2 = svc.add_task("Viết báo cáo", 60, deadline=dt(14, 12))
    plan = svc.suggest_schedule(TOMORROW, TOMORROW)
    assert [(i.title, i.start, i.end) for i in plan.items] == [
        ("Viết báo cáo", dt(14, 9, 10), dt(14, 10, 10)),
        ("Học tiếng Anh", dt(14, 10, 20), dt(14, 12, 20)),
    ]
    assert svc.list_events(TOMORROW, TOMORROW)[-1].title == "Họp"  # đề xuất chưa tạo sự kiện nào

    created = svc.apply_schedule(plan.plan_id)
    assert [(e.title, e.start_at) for e in created] == [(i.title, i.start) for i in plan.items]
    assert {t.id: t.status for t in svc.list_tasks()} == {t1.id: "scheduled", t2.id: "scheduled"}
    with pytest.raises(ScheduleError, match="đã ở trạng thái 'applied'"):
        svc.apply_schedule(plan.plan_id)


def test_apply_refuses_stale_plan(svc):
    svc.add_task("Học", 60)
    plan = svc.suggest_schedule(TOMORROW, TOMORROW)
    first = plan.items[0]
    svc.create_event("Việc mới chen vào", first.start, duration_min=30)
    with pytest.raises(ScheduleError, match="Lịch đã thay đổi"):
        svc.apply_schedule(plan.plan_id)


def test_deleting_event_puts_task_back_to_todo(svc):
    svc.add_task("Học", 60)
    (event,) = svc.apply_schedule(svc.suggest_schedule(TOMORROW, TOMORROW).plan_id)
    svc.delete_event(event.id)
    assert svc.list_tasks()[0].status == "todo"


def test_tools_schema_and_destructive_delete_blocked(session_factory):
    ex = ToolExecutor(build_schedule_tools(session_factory, now=lambda: NOW))
    r = ex.execute(ToolCall("1", "create_event", {"title": "Họp", "start_at": "2026-11-14T15:00", "duration_min": 60}))
    assert not r.is_error and r.output["event"]["start_at"] == "2026-11-14T15:00:00"
    assert ex.execute(ToolCall("2", "add_task", {"title": "x", "duration_min": 30, "priority": 5})).is_error
    blocked = ex.execute(ToolCall("3", "delete_event", {"event_id": r.output["event"]["id"]}))
    assert blocked.is_error and "duyệt" in blocked.output


def test_agent_creates_event(session_factory):
    llm = FakeLLM([[ToolCall("c", "create_event", {"title": "Họp nhóm", "start_at": "2026-11-14T15:00",
                                                    "duration_min": 60})], "Đã tạo."])
    result = ScheduleAgent(llm, session_factory, now=lambda: NOW).run("chiều mai 3h họp nhóm 1 tiếng")
    assert result.status == "ok"
    with session_scope(session_factory) as s:
        (e,) = ScheduleService(s, now=lambda: NOW).list_events(TOMORROW, TOMORROW + timedelta(days=1))
    assert (e.title, e.start_at) == ("Họp nhóm", dt(14, 15))
