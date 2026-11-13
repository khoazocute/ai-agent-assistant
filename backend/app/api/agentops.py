"""API AgentOps: danh sách run, chi tiết một run (prompt + tool từng bước, run con), số liệu, audit, policy."""

from __future__ import annotations

import dataclasses
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_runtime, require_user
from app.bootstrap import load_pricing
from app.harness.agentops.metrics import agent_stats
from app.harness.agentops.store import AgentRun, child_runs, recent_runs, run_events
from app.harness.evaluation.feedback import FeedbackStore
from app.runtime import Runtime

router = APIRouter(prefix="/api", tags=["agentops"], dependencies=[Depends(require_user)])


def _run(r: AgentRun) -> dict[str, Any]:
    cost_vnd = load_pricing().to_vnd(r.cost_usd)
    return {"run_id": r.run_id, "parent_run_id": r.parent_run_id, "agent": r.agent, "channel": r.channel,
            "model": r.model, "prompt_version": r.prompt_version, "input": r.input, "output": r.output,
            "status": r.status, "error": r.error, "steps": r.steps, "tool_calls": r.tool_calls,
            "input_tokens": r.input_tokens, "output_tokens": r.output_tokens, "thinking_tokens": r.thinking_tokens,
            "cost_vnd": cost_vnd, "latency_ms": r.latency_ms, "started_at": r.started_at, "ended_at": r.ended_at}


@router.get("/runs")
def runs(limit: int = 50, rt: Runtime = Depends(get_runtime)) -> list[dict[str, Any]]:
    return [_run(r) for r in recent_runs(rt.session_factory, min(limit, 200))]


@router.get("/runs/{run_id}")
def run_detail(run_id: str, rt: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    run, events = run_events(rt.session_factory, run_id)
    if run is None:
        raise HTTPException(404, "Không có run này")
    return {"run": _run(run),
            "events": [{"seq": e.seq, "type": e.type, "ts": e.ts, "data": e.data} for e in events],
            "children": [_run(c) for c in child_runs(rt.session_factory, run.run_id)]}


@router.get("/metrics")
def metrics(rt: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    pricing = load_pricing()
    up, down = FeedbackStore(rt.session_factory).ratio()
    return {
        "agents": [dataclasses.asdict(s) | {"success_rate": s.success_rate,
                                            "total_cost_vnd": pricing.to_vnd(s.total_cost_usd)}
                   for s in agent_stats(rt.session_factory)],
        "feedback": {"up": up, "down": down},
        "pending_approvals": len(rt.approvals.list("pending")),
    }


@router.get("/audit")
def audit(limit: int = 100, rt: Runtime = Depends(get_runtime)) -> list[dict[str, Any]]:
    return [{"id": e.id, "ts": e.ts, "actor": e.actor, "action": e.action, "target": e.target, "detail": e.detail}
            for e in rt.audit.recent(min(limit, 500))]


@router.get("/policy")
def policy(rt: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    p = rt.policy.get()
    return {"defaults": p.defaults, "tools": p.tools, "disabled_tools": sorted(p.disabled_tools),
            "disabled_agents": sorted(p.disabled_agents), "approval_ttl_hours": p.approval_ttl_hours}
