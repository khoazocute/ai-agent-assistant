from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_runtime, require_user
from app.harness.orchestration.approvals import ApprovalError, PendingAction
from app.runtime import Runtime

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalOut(BaseModel):
    id: int
    tool: str
    agent: str
    risk: str
    summary: str
    status: str
    run_id: str
    created_at: datetime
    expires_at: datetime
    decided_by: str
    result: Any = None
    error: str

    @classmethod
    def of(cls, pa: PendingAction) -> ApprovalOut:
        return cls(id=pa.id, tool=pa.tool, agent=pa.agent, risk=pa.risk, summary=pa.summary, status=pa.status,
                   run_id=pa.run_id, created_at=pa.created_at, expires_at=pa.expires_at, decided_by=pa.decided_by,
                   result=pa.result, error=pa.error)


class RejectIn(BaseModel):
    reason: str = ""


@router.get("")
def list_approvals(status: str | None = "pending", rt: Runtime = Depends(get_runtime),
                   user: str = Depends(require_user)) -> list[ApprovalOut]:
    return [ApprovalOut.of(pa) for pa in rt.approvals.list(status or None)]


@router.post("/{action_id}/approve")
def approve(action_id: int, rt: Runtime = Depends(get_runtime), user: str = Depends(require_user)) -> ApprovalOut:
    try:
        return ApprovalOut.of(rt.approve(action_id, f"user:web:{user}"))
    except ApprovalError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/{action_id}/reject")
def reject(action_id: int, body: RejectIn | None = None, rt: Runtime = Depends(get_runtime),
           user: str = Depends(require_user)) -> ApprovalOut:
    try:
        return ApprovalOut.of(rt.reject(action_id, f"user:web:{user}", body.reason if body else ""))
    except ApprovalError as e:
        raise HTTPException(409, str(e)) from e
