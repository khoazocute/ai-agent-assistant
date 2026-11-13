"""Số liệu vận hành từ bảng agent_runs: tỉ lệ thành công, độ trễ p50/p95, token, chi phí."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.harness.agentops.store import AgentRun


def percentile(values: list[int], p: float) -> int | None:
    """Phân vị kiểu "nearest-rank": p95 = giá trị mà 95% run nhanh hơn hoặc bằng."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


@dataclass
class AgentStats:
    agent: str
    runs: int
    ok: int
    errors: int
    p50_ms: int | None
    p95_ms: int | None
    avg_input_tokens: int
    avg_output_tokens: int
    avg_steps: float
    total_cost_usd: float | None

    @property
    def success_rate(self) -> float:
        return self.ok / self.runs if self.runs else 0.0


def agent_stats(session_factory: sessionmaker, since: datetime | None = None) -> list[AgentStats]:
    with session_factory() as s:
        q = select(AgentRun).where(AgentRun.status != "running")
        if since:
            q = q.where(AgentRun.started_at >= since)
        runs = list(s.scalars(q))
    by_agent: dict[str, list[AgentRun]] = {}
    for r in runs:
        by_agent.setdefault(r.agent or "?", []).append(r)
    stats = []
    for agent, rs in sorted(by_agent.items()):
        latencies = [r.latency_ms for r in rs if r.latency_ms is not None]
        costs = [r.cost_usd for r in rs if r.cost_usd is not None]
        stats.append(AgentStats(
            agent=agent, runs=len(rs), ok=sum(r.status == "ok" for r in rs),
            errors=sum(r.status == "error" for r in rs),
            p50_ms=percentile(latencies, 50), p95_ms=percentile(latencies, 95),
            avg_input_tokens=round(sum(r.input_tokens for r in rs) / len(rs)),
            avg_output_tokens=round(sum(r.output_tokens + r.thinking_tokens for r in rs) / len(rs)),
            avg_steps=round(sum(r.steps for r in rs) / len(rs), 1),
            total_cost_usd=sum(costs) if costs else None,
        ))
    return stats
