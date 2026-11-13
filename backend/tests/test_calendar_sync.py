"""Đồng bộ hai chiều với Google Calendar (bản giả mô phỏng syncToken + etag)."""

from datetime import datetime

import pytest
from conftest import NOW

from app.db.models import Event
from app.db.session import session_scope
from app.integrations.calendar_provider import FakeCalendarProvider, SyncTokenExpired
from app.services.calendar_sync import CalendarSync
from app.services.schedule_service import ScheduleService


def dt(h: int, day: int = 14) -> datetime:
    return datetime(2026, 11, day, h)


@pytest.fixture
def google():
    return FakeCalendarProvider()


def sync(factory, google):
    with session_scope(factory) as s:
        return CalendarSync(s, google, now=lambda: NOW).run()


def events(factory):
    with session_scope(factory) as s:
        return {e.title: (e.start_at, e.gcal_event_id, e.source) for e in s.query(Event)}


def test_local_event_is_pushed_once(session_factory, google):
    with session_scope(session_factory) as s:
        ScheduleService(s, now=lambda: NOW).create_event("Họp", dt(9), duration_min=60)
    r = sync(session_factory, google)
    assert (r.pushed_new, r.pulled_new, r.pulled_updates) == (1, 0, 0)  # kéo về thấy chính nó → bỏ qua
    (remote,) = google.events.values()
    assert (remote.title, remote.start) == ("Họp", dt(9))
    again = sync(session_factory, google)
    assert again.model_dump() == {**again.model_dump(), "pushed_new": 0, "pushed_updates": 0, "pulled_updates": 0}


def test_remote_changes_are_pulled(session_factory, google):
    google.insert("Khám răng", dt(10), dt(11))
    assert sync(session_factory, google).pulled_new == 1
    assert events(session_factory)["Khám răng"][2] == "gcal"

    gid = next(iter(google.events))
    google.remote_edit(gid, start=dt(15), end=dt(16))
    assert sync(session_factory, google).pulled_updates == 1
    assert events(session_factory)["Khám răng"][0] == dt(15)

    google.delete(gid)
    assert sync(session_factory, google).pulled_deletes == 1
    assert events(session_factory) == {}


def test_local_edit_and_delete_are_pushed(session_factory, google):
    with session_scope(session_factory) as s:
        e = ScheduleService(s, now=lambda: NOW).create_event("Họp", dt(9), duration_min=60).event
    sync(session_factory, google)
    with session_scope(session_factory) as s:
        ScheduleService(s, now=lambda: NOW).update_event(e.id, start_at=dt(13))
    assert sync(session_factory, google).pushed_updates == 1
    assert next(iter(google.events.values())).start == dt(13)

    with session_scope(session_factory) as s:
        ScheduleService(s, now=lambda: NOW).delete_event(e.id)
    assert sync(session_factory, google).pushed_deletes == 1
    assert next(iter(google.events.values())).cancelled


def test_expired_sync_token_triggers_full_resync(session_factory, google):
    google.insert("A", dt(9), dt(10))
    sync(session_factory, google)
    calls = []
    original = google.list_changes

    def flaky(token):
        calls.append(token)
        if token is not None:
            raise SyncTokenExpired()
        return original(None)

    google.list_changes = flaky
    assert sync(session_factory, google).full_resync and calls[-1] is None
    assert list(events(session_factory)) == ["A"]  # đồng bộ lại không nhân đôi
