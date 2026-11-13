"""Job nền (APScheduler, chạy trong event loop của web — bước 16).

    07:00         bản tin sáng           → Telegram
    21:00         tổng kết tối           → Telegram
    mỗi phút      nhắc sự kiện sắp bắt đầu trong 15 phút (mỗi sự kiện nhắc một lần)
    mỗi 10 phút   đồng bộ Google Calendar (nếu đã kết nối)
    mỗi 15 phút   kéo thư mới (nếu đã kết nối Gmail) → báo nếu có thư đáng ngờ
    03:00         dọn trace > 90 ngày, hết hạn yêu cầu duyệt cũ

Mỗi job: phần nặng (DB, LLM, Google API) chạy trong thread (`asyncio.to_thread`) để không chặn web;
lỗi trong một job được ghi log + audit, KHÔNG làm chết scheduler hay job khác.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import now_vn
from app.db.models import Event
from app.db.session import session_scope
from app.notify import Notifier
from app.runtime import Runtime

log = logging.getLogger(__name__)
REMIND_BEFORE = timedelta(minutes=15)
TRACE_RETENTION_DAYS = 90


class Jobs:
    def __init__(self, rt: Runtime, notifier: Notifier, now: Callable[[], datetime] = now_vn,
                 use_llm: bool = True) -> None:
        self.rt = rt
        self.notifier = notifier
        self.now = now
        self.use_llm = use_llm

    # ---------- từng job (async, test gọi trực tiếp được) ----------

    async def brief(self, kind: str) -> str:
        from app.agents.briefing.workflow import compose_brief
        from app.services.briefing_service import BriefingService

        def build() -> str:
            with session_scope(self.rt.session_factory) as s:
                data = BriefingService(s, self.now).collect(kind, len(self.rt.approvals.list("pending")))
            llm = self._llm()
            text, source = compose_brief(llm, data, self.rt.tracer("job"))
            log.info("Bản tin %s (%s)", kind, source)
            return text

        text = await asyncio.to_thread(build)
        await self.notifier.send(text)
        return text

    async def remind_events(self) -> list[str]:
        def due() -> list[str]:
            now = self.now().replace(tzinfo=None)
            with session_scope(self.rt.session_factory) as s:
                events = list(s.scalars(select(Event).where(
                    Event.start_at > now, Event.start_at <= now + REMIND_BEFORE, Event.reminded_at.is_(None))))
                for e in events:
                    e.reminded_at = now  # đánh dấu TRƯỚC khi gửi: thà lỡ một lời nhắc còn hơn nhắc lặp mỗi phút
                return [f"⏰ {e.start_at:%H:%M} — {e.title}" + (f" @ {e.location}" if e.location else "")
                        for e in events]

        messages = await asyncio.to_thread(due)
        for m in messages:
            await self.notifier.send(m)
        return messages

    async def sync_calendar(self) -> None:
        if self.rt.calendar_provider() is not None:
            report = await asyncio.to_thread(self.rt.sync_calendar)
            log.info("Đồng bộ Google Calendar: %s", report.model_dump())

    async def fetch_email(self) -> None:
        from app.integrations.email_provider import NotConnectedEmailProvider
        from app.services.email_service import EmailService

        if isinstance(self.rt.email_provider, NotConnectedEmailProvider):
            return

        def sync():
            with session_scope(self.rt.session_factory) as s:
                return EmailService(s, self.rt.email_provider).sync_inbox()

        result = await asyncio.to_thread(sync)
        if result.flagged:
            await self.notifier.send(f"⚠ {len(result.flagged)} thư mới có dấu hiệu lừa đảo / cố điều khiển trợ lý. "
                                     "Đừng làm theo nội dung thư — xem trên web mục Email.")

    async def cleanup(self) -> dict[str, int]:
        from app.harness.agentops.store import purge_runs_before

        def run() -> dict[str, int]:
            cutoff = self.now().replace(tzinfo=None) - timedelta(days=TRACE_RETENTION_DAYS)
            return {"runs_deleted": purge_runs_before(self.rt.session_factory, cutoff),
                    "approvals_expired": self.rt.approvals.expire_old()}

        result = await asyncio.to_thread(run)
        log.info("Dọn dữ liệu: %s", result)
        return result

    # ---------- nội bộ ----------

    def _llm(self):
        if not self.use_llm:
            return None
        try:
            return self.rt.llm
        except RuntimeError:  # thiếu API key → dùng mẫu dựng sẵn
            return None

    async def safe(self, name: str, coro_fn: Callable, *args) -> None:
        try:
            await coro_fn(*args)
        except Exception as e:  # một job lỗi không được làm chết scheduler
            log.exception("Job %s lỗi", name)
            await asyncio.to_thread(self.rt.audit.record, "system", f"job:{name}:error", "", {"error": str(e)})


def build_scheduler(jobs: Jobs):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    tz = "Asia/Ho_Chi_Minh"
    sched = AsyncIOScheduler(timezone=tz)
    # max_instances=1 + coalesce: job chạy lâu (vd. Google chậm) không bị chồng nhiều bản cùng lúc.
    common = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 300}
    sched.add_job(jobs.safe, CronTrigger(hour=7, minute=0, timezone=tz), args=["morning", jobs.brief, "morning"],
                  id="morning_brief", **common)
    sched.add_job(jobs.safe, CronTrigger(hour=21, minute=0, timezone=tz), args=["evening", jobs.brief, "evening"],
                  id="evening_brief", **common)
    sched.add_job(jobs.safe, IntervalTrigger(minutes=1), args=["remind", jobs.remind_events], id="remind_events",
                  **common)
    sched.add_job(jobs.safe, IntervalTrigger(minutes=10), args=["gcal", jobs.sync_calendar], id="gcal_sync", **common)
    sched.add_job(jobs.safe, IntervalTrigger(minutes=15), args=["email", jobs.fetch_email], id="fetch_email",
                  **common)
    sched.add_job(jobs.safe, CronTrigger(hour=3, minute=0, timezone=tz), args=["cleanup", jobs.cleanup],
                  id="cleanup", **common)
    return sched
