"""Lưu trace vào DB (ADR-0006).

Hai bảng:
  agent_runs    MỘT dòng mỗi run — tổng hợp để thống kê nhanh (agent, trạng thái, token, chi phí, độ trễ)
  agent_events  MỌI sự kiện của run, nguyên văn JSON — để xem lại chính xác prompt/tool từng bước

Vì sao lưu sự kiện dạng JSON thay vì nhiều bảng cột cố định: loại sự kiện còn thay đổi theo các bước
(thêm duyệt, thêm sub-agent…), JSON không cần migration mỗi lần; còn những gì cần lọc/thống kê
thì được rút ra cột riêng ở agent_runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.harness.agentops.cost import Pricing
from app.harness.storage import HarnessBase


class AgentRun(HarnessBase):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(40), index=True)
    agent: Mapped[str] = mapped_column(String(40), index=True, default="")
    channel: Mapped[str] = mapped_column(String(20), default="")  # cli | telegram | web | eval | job
    model: Mapped[str] = mapped_column(String(80), default="")
    prompt_version: Mapped[str] = mapped_column(String(20), default="")
    input: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[int] = mapped_column(default=0)
    tool_calls: Mapped[int] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    thinking_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float | None]
    latency_ms: Mapped[int | None]
    started_at: Mapped[datetime] = mapped_column(index=True)
    ended_at: Mapped[datetime | None]


class AgentEvent(HarnessBase):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.run_id", ondelete="CASCADE"), index=True)
    seq: Mapped[int]
    type: Mapped[str] = mapped_column(String(30))
    ts: Mapped[datetime]
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class DbTraceSink:
    """Sink ghi vào DB. Mỗi sự kiện một phiên ngắn → run chết giữa chừng vẫn còn dữ liệu đến lúc đó."""

    def __init__(self, session_factory: sessionmaker, pricing: Pricing | None = None, channel: str = "") -> None:
        self.factory = session_factory
        self.pricing = pricing or Pricing()
        self.channel = channel
        self._seq: dict[str, int] = {}

    def write(self, record: dict[str, Any]) -> None:
        run_id, type_ = record["run_id"], record["type"]
        ts = datetime.fromisoformat(record["ts"]).replace(tzinfo=None)  # lưu giờ VN không kèm múi giờ
        data = {k: v for k, v in record.items() if k not in ("run_id", "type", "ts")}
        seq = self._seq[run_id] = self._seq.get(run_id, 0) + 1

        with self.factory() as s, s.begin():
            if type_ == "run_start":
                s.add(AgentRun(
                    run_id=run_id, parent_run_id=record.get("parent_run_id"), agent=record.get("agent") or "",
                    channel=record.get("channel") or self.channel, model=record.get("model") or "",
                    prompt_version=record.get("prompt_version") or "", input=record.get("input") or "",
                    started_at=ts, cost_usd=None, latency_ms=None, ended_at=None,
                ))
                s.flush()
            run = s.get(AgentRun, run_id)
            if run is not None:
                self._update_run(run, type_, record, ts)
            s.add(AgentEvent(run_id=run_id, seq=seq, type=type_, ts=ts, data=data))

    def _update_run(self, run: AgentRun, type_: str, r: dict[str, Any], ts: datetime) -> None:
        if type_ == "tool_call":
            run.tool_calls += 1
        elif type_ == "run_end":
            u = r.get("usage", {})
            run.status = r.get("status", "")
            run.output = r.get("answer") or ""
            run.error = r.get("error") or ""
            run.steps = r.get("steps", 0)
            run.input_tokens = u.get("input_tokens", 0)
            run.output_tokens = u.get("output_tokens", 0)
            run.thinking_tokens = u.get("thinking_tokens", 0)
            run.cost_usd = self.pricing.cost_usd(run.model, run.input_tokens, run.output_tokens, run.thinking_tokens)
            run.ended_at = ts
            run.latency_ms = round((ts - run.started_at).total_seconds() * 1000)


# ---------- Đọc lại ----------

def recent_runs(session_factory: sessionmaker, limit: int = 20, top_level_only: bool = True) -> list[AgentRun]:
    with session_factory() as s:
        q = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
        if top_level_only:
            q = q.where(AgentRun.parent_run_id.is_(None))
        return list(s.scalars(q))


def run_events(session_factory: sessionmaker, run_id: str) -> tuple[AgentRun | None, list[AgentEvent]]:
    """Run + sự kiện của nó; run_id được phép là tiền tố (gõ tắt trên CLI)."""
    with session_factory() as s:
        run = s.get(AgentRun, run_id) or s.scalars(
            select(AgentRun).where(AgentRun.run_id.startswith(run_id)).order_by(AgentRun.started_at.desc())
        ).first()
        if run is None:
            return None, []
        events = list(s.scalars(select(AgentEvent).where(AgentEvent.run_id == run.run_id).order_by(AgentEvent.seq)))
        return run, events


def child_runs(session_factory: sessionmaker, run_id: str) -> list[AgentRun]:
    with session_factory() as s:
        return list(s.scalars(select(AgentRun).where(AgentRun.parent_run_id == run_id)
                              .order_by(AgentRun.started_at)))
