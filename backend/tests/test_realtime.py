"""Realtime: commit DB ở bất kỳ đâu → EventBus phát đúng chủ đề → SSE."""

import asyncio
from datetime import date

from app.db.session import session_scope
from app.realtime import EventBus, install_change_listener
from app.services.finance_service import FinanceService


def test_commit_publishes_topics_once_and_rollback_publishes_nothing(session_factory):
    bus = EventBus()
    published: list[str] = []
    bus.publish = lambda topic, **_: published.append(topic)  # bắt lời gọi, không cần event loop
    install_change_listener(session_factory, bus)

    with session_scope(session_factory) as s:
        svc = FinanceService(s, today=lambda: date(2026, 11, 13))
        svc.add_transaction(45000, "an_uong")
        svc.add_transaction(60000, "di_chuyen")
    assert published == ["finance"]  # 2 dòng, 1 commit → 1 sự kiện

    published.clear()
    try:
        with session_scope(session_factory) as s:
            FinanceService(s, today=lambda: date(2026, 11, 13)).add_transaction(1, "an_uong")
            raise RuntimeError("lỗi giữa chừng")
    except RuntimeError:
        pass
    assert published == []  # rollback → không báo dữ liệu đổi


def test_bus_delivers_to_subscribers_from_other_threads():
    async def scenario() -> list[str]:
        bus = EventBus()
        bus.bind(asyncio.get_running_loop())
        stream = bus.subscribe(keepalive_s=5)
        assert await anext(stream) == ": connected\n\n"
        await asyncio.to_thread(bus.publish, "schedule")  # như agent chạy trong threadpool
        line = await asyncio.wait_for(anext(stream), 2)
        await stream.aclose()
        return [line, str(bus.subscriber_count)]

    line, remaining = asyncio.run(scenario())
    assert line == 'data: {"topic": "schedule"}\n\n' and remaining == "0"


def test_publish_without_loop_is_noop():
    EventBus().publish("finance")  # không lỗi khi chưa có web (CLI, test)
