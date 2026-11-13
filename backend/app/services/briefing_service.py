"""Gom số liệu cho bản tin sáng/tối — BẰNG CODE, không LLM (ADR-0014).

Mọi con số, giờ giấc trong bản tin lấy từ đây → khớp 100% với DB. LLM chỉ viết lời từ dữ liệu đã có.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import now_vn
from app.db.models import Email, Task, TaskStatus
from app.services.finance_service import FinanceService, resolve_period
from app.services.schedule_service import ScheduleService


class BriefEvent(BaseModel):
    title: str
    start: str  # "HH:MM"
    end: str


class BriefTask(BaseModel):
    title: str
    duration_min: int
    deadline: str | None


class BriefEmail(BaseModel):
    from_addr: str
    subject: str
    category: str | None
    suspicious: bool


class BriefData(BaseModel):
    kind: str  # morning | evening
    day: date
    events_today: list[BriefEvent]
    events_tomorrow: list[BriefEvent]
    tasks_due_soon: list[BriefTask]  # việc chưa xong có hạn trong 3 ngày tới
    spent_today_vnd: int
    spent_yesterday_vnd: int
    month_expense_vnd: int
    month_income_vnd: int
    month_net_vnd: int
    top_categories_today: list[tuple[str, int]]
    new_emails: list[BriefEmail]
    pending_approvals: int


class BriefingService:
    def __init__(self, session: Session, now: Callable[[], datetime] = now_vn) -> None:
        self.s = session
        self.now = now

    def collect(self, kind: str, pending_approvals: int = 0) -> BriefData:
        now = self.now()
        today = now.date()
        fin = FinanceService(self.s, today=lambda: today)
        sched = ScheduleService(self.s, now=self.now)
        day_summary = fin.get_summary(today, today)
        month = fin.get_summary(*resolve_period("this_month", today))
        # Mail mới: sáng = từ 21h hôm qua; tối = từ 7h sáng nay. Nội dung KHÔNG đưa vào bản tin (không tin cậy),
        # chỉ người gửi + tiêu đề + cờ đáng ngờ.
        since = (datetime.combine(today - timedelta(days=1), time(21)) if kind == "morning"
                 else datetime.combine(today, time(7)))
        emails = self.s.scalars(select(Email).where(Email.received_at >= since).order_by(Email.received_at.desc())
                                .limit(10))
        due = self.s.scalars(select(Task).where(
            Task.status != TaskStatus.DONE, Task.deadline.is_not(None),
            Task.deadline <= datetime.combine(today + timedelta(days=3), time.max)).order_by(Task.deadline))
        return BriefData(
            kind=kind, day=today,
            events_today=[_ev(e) for e in sched.list_events(today, today)],
            events_tomorrow=[_ev(e) for e in sched.list_events(today + timedelta(days=1), today + timedelta(days=1))],
            tasks_due_soon=[BriefTask(title=t.title, duration_min=t.duration_min,
                                      deadline=t.deadline.strftime("%H:%M %d/%m") if t.deadline else None)
                            for t in due],
            spent_today_vnd=day_summary.total_expense_vnd,
            spent_yesterday_vnd=fin.get_summary(today - timedelta(days=1), today - timedelta(days=1)).total_expense_vnd,
            month_expense_vnd=month.total_expense_vnd, month_income_vnd=month.total_income_vnd,
            month_net_vnd=month.net_spending_vnd,
            top_categories_today=[(c.category_name, c.amount_vnd) for c in day_summary.by_category
                                  if c.kind == "expense"][:3],
            new_emails=[BriefEmail(from_addr=e.from_addr, subject=e.subject, category=e.category,
                                   suspicious=bool(e.injection_flags)) for e in emails],
            pending_approvals=pending_approvals,
        )


def _ev(e) -> BriefEvent:  # noqa: ANN001
    return BriefEvent(title=e.title, start=e.start_at.strftime("%H:%M"), end=e.end_at.strftime("%H:%M"))


def vnd(n: int) -> str:
    return f"{n:,}đ".replace(",", ".")


def fallback_text(d: BriefData) -> str:
    """Bản tin dựng bằng mẫu cố định — dùng khi LLM lỗi/hết quota: bản tin vẫn luôn được gửi."""
    head = (f"☀️ Chào buổi sáng! Hôm nay {d.day:%d/%m}" if d.kind == "morning"
            else f"🌙 Tổng kết ngày {d.day:%d/%m}")
    lines = [head]
    events = d.events_today if d.kind == "morning" else d.events_tomorrow
    label = "Lịch hôm nay" if d.kind == "morning" else "Lịch ngày mai"
    lines.append(f"\n📅 {label}: " + (", ".join(f"{e.start} {e.title}" for e in events) or "trống"))
    if d.kind == "morning":
        lines.append(f"💸 Hôm qua chi {vnd(d.spent_yesterday_vnd)} · tháng này {vnd(d.month_expense_vnd)}")
    else:
        top = ", ".join(f"{name} {vnd(a)}" for name, a in d.top_categories_today)
        lines.append(f"💸 Hôm nay chi {vnd(d.spent_today_vnd)}" + (f" ({top})" if top else ""))
        lines.append(f"   Tháng này: chi {vnd(d.month_expense_vnd)}, thu {vnd(d.month_income_vnd)}, "
                     f"chi ròng {vnd(d.month_net_vnd)}")
    if d.tasks_due_soon:
        lines.append("✅ Việc sắp đến hạn: " + ", ".join(f"{t.title} ({t.deadline})" for t in d.tasks_due_soon))
    if d.new_emails:
        lines.append(f"✉️ {len(d.new_emails)} thư mới" +
                     (f" — ⚠ {sum(e.suspicious for e in d.new_emails)} thư đáng ngờ" if any(
                         e.suspicious for e in d.new_emails) else ""))
    if d.pending_approvals:
        lines.append(f"🔐 {d.pending_approvals} yêu cầu đang chờ duyệt (/approvals)")
    return "\n".join(lines)
