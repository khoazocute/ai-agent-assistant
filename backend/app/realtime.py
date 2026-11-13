"""Realtime: dữ liệu đổi ở BẤT KỲ đâu (Telegram, agent, web, job) → website cập nhật ngay (ADR-0016).

    commit DB ──(SQLAlchemy after_commit)──▶ EventBus.publish(topic) ──▶ hàng đợi của mỗi trình duyệt
                                                                       ──▶ GET /api/stream (SSE)

Vì sao bắt ở tầng DB thay vì gọi publish trong từng service: mọi đường ghi (tool của agent, API web,
duyệt, job nền) đều đi qua session → không thể quên publish ở một chỗ nào đó.
Vì sao SSE thay vì WebSocket: chỉ cần server → trình duyệt một chiều; SSE là HTTP thường, tự kết nối lại,
đi qua proxy dễ, không cần thư viện.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

# bảng → chủ đề mà giao diện quan tâm (agent_events bỏ qua: quá nhiều, đã gộp vào agent_runs)
TABLE_TOPICS = {
    "transactions": "finance", "categories": "finance",
    "events": "schedule", "tasks": "schedule", "schedule_plans": "schedule",
    "emails": "email", "email_drafts": "email",
    "pending_actions": "approvals",
    "agent_runs": "runs", "feedback": "runs",
}


class EventBus:
    """Pub/sub trong tiến trình. publish() gọi được từ thread bất kỳ (agent chạy trong threadpool)."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, topic: str, **data: Any) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        message = {"topic": topic, **data}
        for queue in list(self._subscribers):
            self._loop.call_soon_threadsafe(_put_latest, queue, message)

    async def subscribe(self, keepalive_s: float = 15.0) -> AsyncIterator[str]:
        """Sinh các dòng SSE. Dòng bắt đầu bằng ':' là comment giữ kết nối (proxy hay cắt kết nối im lặng)."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=keepalive_s)
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


def _put_latest(queue: asyncio.Queue[dict[str, Any]], message: dict[str, Any]) -> None:
    if queue.full():  # trình duyệt chậm → bỏ tin cũ nhất, không chặn cả hệ thống
        queue.get_nowait()
    queue.put_nowait(message)


def install_change_listener(factory: sessionmaker, bus: EventBus) -> None:
    @event.listens_for(factory, "after_flush")
    def collect(session: Session, _ctx: Any) -> None:
        topics = session.info.setdefault("changed_topics", set())
        for obj in [*session.new, *session.dirty, *session.deleted]:
            topic = TABLE_TOPICS.get(getattr(obj, "__tablename__", ""))
            if topic:
                topics.add(topic)

    @event.listens_for(factory, "after_commit")
    def publish(session: Session) -> None:
        for topic in session.info.pop("changed_topics", set()):
            bus.publish(topic)

    @event.listens_for(factory, "after_rollback")
    def discard(session: Session) -> None:
        session.info.pop("changed_topics", None)
