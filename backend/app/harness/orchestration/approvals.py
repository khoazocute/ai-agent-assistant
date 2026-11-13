"""Yêu cầu duyệt (PendingAction) — human-in-the-loop cho hành động rủi ro (ADR-0010).

Vòng đời:   pending ──approve──▶ executed | failed
               │ └───reject───▶ rejected
               └───(quá hạn)──▶ expired

Điểm then chốt: khi người dùng bấm DUYỆT, code chạy ĐÚNG tool + tham số đã lưu lúc tạo yêu cầu —
không gọi lại LLM, không "hỏi lại model xem nên làm gì". Thứ người dùng nhìn thấy = thứ được thực hiện.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy import JSON, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.harness.governance.audit import AuditLog
from app.harness.storage import HarnessBase

_VN = timezone(timedelta(hours=7))


def _now() -> datetime:
    return datetime.now(_VN).replace(tzinfo=None)


class PendingAction(HarnessBase):
    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tool: Mapped[str] = mapped_column(String(80))
    agent: Mapped[str] = mapped_column(String(40), default="")
    risk: Mapped[str] = mapped_column(String(20), default="")
    args: Mapped[dict[str, Any]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text, default="")  # mô tả cho người duyệt (vd. nội dung thư sẽ gửi)
    run_id: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    expires_at: Mapped[datetime]
    decided_at: Mapped[datetime | None]
    decided_by: Mapped[str] = mapped_column(String(80), default="")
    result: Mapped[Any] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")


class ApprovalError(ValueError):
    pass


class ApprovalStore:
    def __init__(self, session_factory: sessionmaker, audit: AuditLog | None = None, ttl_hours: float = 24) -> None:
        self.factory = session_factory
        self.audit = audit or AuditLog(session_factory)
        self.ttl = timedelta(hours=ttl_hours)
        # Ai cần biết khi có yêu cầu mới (Telegram gửi nút Duyệt/Từ chối, web cập nhật realtime…)
        self.listeners: list[Callable[[PendingAction], None]] = []

    def create(self, tool: str, args: dict[str, Any], *, agent: str = "", risk: str = "", summary: str = "",
               run_id: str = "") -> PendingAction:
        with self.factory() as s, s.begin():
            pa = PendingAction(tool=tool, agent=agent, risk=risk, args=to_jsonable_python(args), summary=summary,
                               run_id=run_id, expires_at=_now() + self.ttl, decided_at=None, result=None)
            s.add(pa)
            s.flush()
            s.expunge(pa)
        self.audit.record(f"agent:{agent}", "approval:requested", f"pending#{pa.id}", {"tool": tool, "args": pa.args})
        for listener in self.listeners:
            try:
                listener(pa)
            except Exception:  # thông báo lỗi không được làm hỏng việc tạo yêu cầu
                pass
        return pa

    def get(self, action_id: int) -> PendingAction | None:
        with self.factory() as s:
            return s.get(PendingAction, action_id)

    def list(self, status: str | None = "pending", limit: int = 50) -> list[PendingAction]:
        self.expire_old()
        with self.factory() as s:
            q = select(PendingAction).order_by(PendingAction.id.desc()).limit(limit)
            if status:
                q = q.where(PendingAction.status == status)
            return list(s.scalars(q))

    def approve(self, action_id: int, actor: str, tools: Mapping[str, Any]) -> PendingAction:
        """Duyệt và THỰC THI ngay tool đã lưu với đúng tham số đã lưu. `tools`: tên → RegisteredTool."""
        pa = self._decide(action_id, actor, "approved")
        tool = tools.get(pa.tool)
        try:
            if tool is None:
                raise ApprovalError(f"Không tìm thấy tool '{pa.tool}' để thực thi.")
            args = tool.args_model.model_validate(pa.args)  # kiểm tra lại: dữ liệu lưu có thể đã cũ/hỏng
            output = tool.fn(**{k: getattr(args, k) for k in type(args).model_fields})
            status, result, error = "executed", to_jsonable_python(output, fallback=str), ""
        except Exception as e:
            status, result, error = "failed", None, f"{type(e).__name__}: {e}"
        with self.factory() as s, s.begin():
            row = s.get(PendingAction, action_id)
            row.status, row.result, row.error = status, result, error
            s.flush()
            s.expunge(row)
        self.audit.record(actor, f"approval:{status}", f"pending#{action_id}",
                          {"tool": pa.tool, "args": pa.args, "error": error})
        return row

    def reject(self, action_id: int, actor: str, reason: str = "") -> PendingAction:
        pa = self._decide(action_id, actor, "rejected", reason)
        self.audit.record(actor, "approval:rejected", f"pending#{action_id}", {"tool": pa.tool, "reason": reason})
        return pa

    def expire_old(self) -> int:
        with self.factory() as s, s.begin():
            rows = list(s.scalars(select(PendingAction).where(
                PendingAction.status == "pending", PendingAction.expires_at < _now())))
            for row in rows:
                row.status = "expired"
        return len(rows)

    def _decide(self, action_id: int, actor: str, status: str, reason: str = "") -> PendingAction:
        self.expire_old()
        with self.factory() as s, s.begin():
            row = s.get(PendingAction, action_id)
            if row is None:
                raise ApprovalError(f"Không có yêu cầu duyệt #{action_id}.")
            if row.status != "pending":
                # Chống bấm hai lần / duyệt yêu cầu đã hết hạn.
                raise ApprovalError(f"Yêu cầu #{action_id} đang ở trạng thái '{row.status}', không quyết lại được.")
            row.status, row.decided_at, row.decided_by = status, _now(), actor
            if reason:
                row.error = reason
            s.flush()
            s.expunge(row)
        return row
