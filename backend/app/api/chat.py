from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.approvals import ApprovalOut
from app.api.deps import get_runtime, require_user
from app.chat import ChatService
from app.runtime import Runtime

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatOut(BaseModel):
    answer: str
    run_id: str
    status: str
    tools_used: list[str]
    approvals: list[ApprovalOut]


class FeedbackIn(BaseModel):
    run_id: str
    rating: int = Field(ge=-1, le=1)


@router.post("")
async def chat(body: ChatIn, rt: Runtime = Depends(get_runtime), user: str = Depends(require_user)) -> ChatOut:
    # Agent chạy đồng bộ (vài giây – vài chục giây) → đẩy sang threadpool để server vẫn phục vụ request khác.
    reply = await run_in_threadpool(ChatService(rt).handle, "web", user, body.message)
    return ChatOut(answer=reply.answer, run_id=reply.run_id, status=reply.status, tools_used=reply.tools_used,
                   approvals=[ApprovalOut.of(pa) for pa in reply.approvals])


@router.post("/reset")
def reset(rt: Runtime = Depends(get_runtime), user: str = Depends(require_user)) -> dict:
    ChatService(rt).reset("web", user)
    return {"ok": True}


@router.post("/feedback")
def feedback(body: FeedbackIn, rt: Runtime = Depends(get_runtime), user: str = Depends(require_user)) -> dict:
    ChatService(rt).feedback.record(body.run_id, body.rating, "web")
    return {"ok": True}
