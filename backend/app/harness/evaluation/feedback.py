"""Online eval — phản hồi 👍/👎 của người dùng thật cho từng câu trả lời.

Đây là nguồn ca eval tốt nhất: một 👎 kèm trace (run_id) cho biết chính xác agent đã đọc gì, gọi tool gì.
Quy trình: xem `python -m app.cli feedback` → mở `python -m app.cli run <run_id>` → viết thành ca mới trong
evals/cases/*.yaml → sửa prompt/tool → eval lại.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.harness.storage import HarnessBase

_VN = timezone(timedelta(hours=7))


class Feedback(HarnessBase):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    rating: Mapped[int]  # +1 | -1
    channel: Mapped[str] = mapped_column(String(20), default="")
    comment: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(_VN).replace(tzinfo=None))


class FeedbackStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.factory = session_factory

    def record(self, run_id: str, rating: int, channel: str = "", comment: str = "") -> None:
        if rating not in (1, -1):
            raise ValueError("rating phải là +1 hoặc -1")
        with self.factory() as s, s.begin():
            s.add(Feedback(run_id=run_id, rating=rating, channel=channel, comment=comment[:1000]))

    def recent(self, limit: int = 50, only_negative: bool = False) -> list[Feedback]:
        with self.factory() as s:
            q = select(Feedback).order_by(Feedback.id.desc()).limit(limit)
            if only_negative:
                q = q.where(Feedback.rating < 0)
            return list(s.scalars(q))

    def ratio(self) -> tuple[int, int]:
        """(số 👍, số 👎)."""
        rows = self.recent(limit=100_000)
        return sum(r.rating > 0 for r in rows), sum(r.rating < 0 for r in rows)
