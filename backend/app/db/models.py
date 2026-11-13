"""Bảng dữ liệu (SQLAlchemy 2, kiểu khai báo có type hint).

Quy ước:
- Tiền là **số nguyên VND** (`amount_vnd: int`), luôn dương. Thu hay chi do `Category.kind` quyết định,
  không dùng số âm — tránh lỗi dấu và lỗi làm tròn của float.
- Ngày giao dịch (`occurred_on`) là ngày theo giờ Việt Nam; `created_at` là thời điểm ghi (có múi giờ).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import now_vn


class Base(DeclarativeBase):
    pass


class CategoryKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


class Category(Base):
    __tablename__ = "categories"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)  # vd. "an_uong" — ổn định, dùng trong tool
    name_vi: Mapped[str] = mapped_column(String(80))  # vd. "Ăn uống" — để hiển thị
    kind: Mapped[CategoryKind] = mapped_column(String(10))


class Transaction(Base):
    __tablename__ = "transactions"
    # Luật ở tầng DB: kể cả code có bug, DB vẫn không nhận số tiền <= 0.
    __table_args__ = (CheckConstraint("amount_vnd > 0", name="ck_transactions_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    amount_vnd: Mapped[int]
    category_key: Mapped[str] = mapped_column(ForeignKey("categories.key"), index=True)
    occurred_on: Mapped[date] = mapped_column(index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(default=now_vn)

    category: Mapped[Category] = relationship(lazy="joined")


# ---------- Lịch (bước 7) ----------
# Thời gian lưu là giờ Việt Nam KHÔNG kèm múi giờ (naive): app một người dùng ở VN; SQLite không lưu
# múi giờ. Mọi đầu vào có múi giờ được quy về giờ VN ở service trước khi lưu.


class TaskStatus(StrEnum):
    TODO = "todo"
    SCHEDULED = "scheduled"
    DONE = "done"


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (CheckConstraint("end_at > start_at", name="ck_events_end_after_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    start_at: Mapped[datetime] = mapped_column(index=True)
    end_at: Mapped[datetime] = mapped_column(index=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(String(1000), default="")
    source: Mapped[str] = mapped_column(String(20), default="local")  # local | gcal
    gcal_event_id: Mapped[str | None] = mapped_column(String(200), unique=True)  # bước 15
    etag: Mapped[str | None] = mapped_column(String(200))
    synced_at: Mapped[datetime | None]  # lần cuối khớp với Google; NULL = có thay đổi local chưa đẩy lên
    updated_at: Mapped[datetime] = mapped_column(default=lambda: now_vn().replace(tzinfo=None),
                                                 onupdate=lambda: now_vn().replace(tzinfo=None))


class Task(Base):
    """Việc cần làm chưa có giờ cố định — planner sẽ tìm chỗ trống cho nó."""

    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("duration_min > 0", name="ck_tasks_duration_positive"),
                      CheckConstraint("priority BETWEEN 1 AND 3", name="ck_tasks_priority"))

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    duration_min: Mapped[int]
    deadline: Mapped[datetime | None]
    priority: Mapped[int] = mapped_column(default=2)  # 1 cao · 2 thường · 3 thấp
    status: Mapped[TaskStatus] = mapped_column(String(12), default=TaskStatus.TODO, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: now_vn().replace(tzinfo=None))


class SchedulePlan(Base):
    """Phương án xếp lịch ĐỀ XUẤT. Chỉ thành sự kiện thật khi apply — người dùng xem trước rồi mới đồng ý."""

    __tablename__ = "schedule_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(12), default="proposed")  # proposed | applied | discarded
    items: Mapped[list[dict]] = mapped_column(JSON)  # [{task_id, title, start, end}]
    unscheduled: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=lambda: now_vn().replace(tzinfo=None))


# ---------- Email (bước 10) ----------
# Nội dung email là DỮ LIỆU KHÔNG TIN CẬY: lưu nguyên văn, chỉ bọc <untrusted_content> khi đưa cho model.


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(200), unique=True)
    thread_id: Mapped[str] = mapped_column(String(200), default="")
    message_id_header: Mapped[str] = mapped_column(String(500), default="")
    from_addr: Mapped[str] = mapped_column(String(500))
    to_addrs: Mapped[str] = mapped_column(String(2000), default="")
    subject: Mapped[str] = mapped_column(String(1000), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(index=True)
    category: Mapped[str | None] = mapped_column(String(20))  # important | needs_reply | newsletter | other
    summary: Mapped[str] = mapped_column(String(1000), default="")
    injection_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    fetched_at: Mapped[datetime] = mapped_column(default=lambda: now_vn().replace(tzinfo=None))


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_addrs: Mapped[str] = mapped_column(String(2000))
    subject: Mapped[str] = mapped_column(String(1000))
    body: Mapped[str] = mapped_column(Text)
    reply_to_email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft | sent | discarded
    pii_warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=lambda: now_vn().replace(tzinfo=None))
    sent_at: Mapped[datetime | None]


# ---------- Đồng bộ Google Calendar (bước 15) ----------


class CalendarTombstone(Base):
    """Sự kiện đã xoá ở máy mình nhưng còn trên Google → lần đồng bộ sau sẽ xoá bên Google."""

    __tablename__ = "calendar_tombstones"

    gcal_event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    deleted_at: Mapped[datetime] = mapped_column(default=lambda: now_vn().replace(tzinfo=None))


class SyncState(Base):
    """Trạng thái đồng bộ dạng khoá–giá trị (vd. syncToken của Google Calendar)."""

    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
