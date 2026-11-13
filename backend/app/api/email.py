from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db, get_runtime, require_user
from app.db.models import Email
from app.runtime import Runtime
from app.services.email_service import DraftOut, EmailService, SyncResult

router = APIRouter(prefix="/api/emails", tags=["email"], dependencies=[Depends(require_user)])


class EmailView(BaseModel):
    """Hiển thị cho NGƯỜI (React tự escape HTML) — không bọc <untrusted_content> như khi đưa cho model."""

    id: int
    from_addr: str
    subject: str
    snippet: str
    received_at: datetime
    category: str | None
    summary: str
    injection_flags: list[str]


@router.get("")
def list_emails(limit: int = 50, s: Session = Depends(db)) -> list[EmailView]:
    rows = s.scalars(select(Email).order_by(Email.received_at.desc()).limit(min(limit, 200)))
    return [EmailView(id=e.id, from_addr=e.from_addr, subject=e.subject, snippet=" ".join(e.body.split())[:300],
                      received_at=e.received_at, category=e.category, summary=e.summary,
                      injection_flags=e.injection_flags) for e in rows]


@router.post("/sync")
def sync(s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> SyncResult:
    try:
        return EmailService(s, rt.email_provider).sync_inbox()
    except RuntimeError as e:  # chưa kết nối Gmail
        raise HTTPException(409, str(e)) from e


@router.get("/drafts")
def drafts(s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> list[DraftOut]:
    return EmailService(s, rt.email_provider).list_drafts(status=None)


@router.post("/drafts/{draft_id}/discard")
def discard(draft_id: int, s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> DraftOut:
    return EmailService(s, rt.email_provider).discard_draft(draft_id)
