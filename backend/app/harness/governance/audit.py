"""Audit log — ai đã làm gì, lúc nào, với dữ liệu nào. Chỉ ghi thêm, không sửa/xoá.

Ghi: mọi tool ghi/xoá/gửi đã thực thi, mọi quyết định duyệt/từ chối, mọi lần bị policy từ chối.
Trace (AgentOps) trả lời "agent đã nghĩ gì"; audit trả lời "điều gì đã THỰC SỰ thay đổi và ai cho phép".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import JSON, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.harness.storage import HarnessBase

_VN = timezone(timedelta(hours=7))


def _now() -> datetime:
    return datetime.now(_VN).replace(tzinfo=None)


class AuditEntry(HarnessBase):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(default=_now, index=True)
    actor: Mapped[str] = mapped_column(String(80))  # "agent:finance" | "user:telegram" | "user:web" | "system"
    action: Mapped[str] = mapped_column(String(80), index=True)  # "tool:add_transaction" | "approval:approve" …
    target: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditLog:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.factory = session_factory

    def record(self, actor: str, action: str, target: str = "", detail: dict[str, Any] | None = None,
               session: Session | None = None) -> None:
        """`session` có sẵn → ghi trong CÙNG transaction với thay đổi (cùng commit/rollback, không tranh khoá
        ghi với chính mình trên SQLite). Không có → tự mở phiên ngắn."""
        entry = AuditEntry(actor=actor, action=action, target=target, detail=detail or {})
        if session is not None:
            session.add(entry)
            return
        with self.factory() as s, s.begin():
            s.add(entry)

    def recent(self, limit: int = 50) -> list[AuditEntry]:
        with self.factory() as s:
            return list(s.scalars(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit)))
