"""Nghiệp vụ email: kéo thư về, phân loại, soạn nháp, gửi (CHỈ sau khi được duyệt — bước 11).

Ranh giới tin cậy (ADR-0009):
  - Mọi trường đến từ bên ngoài (người gửi, tiêu đề, nội dung) khi đưa cho model đều được bọc
    <untrusted_content> và kèm cờ `injection_flags` nếu có dấu hiệu ra lệnh cho AI.
  - Bản nháp được quét PII (`pii_warnings`) để người duyệt nhìn thấy trước khi gửi.
  - `send_draft` gửi ĐÚNG nội dung bản nháp đã lưu — không nhận nội dung mới lúc gửi.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import now_vn
from app.db.models import Email, EmailDraft
from app.harness.security.pii import scan_pii
from app.harness.security.sanitizer import detect_injection, wrap_untrusted
from app.integrations.email_provider import EmailProvider

CATEGORIES = ("important", "needs_reply", "newsletter", "other")
_EMAIL_ADDR = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


class EmailError(ValueError):
    pass


class EmailListItem(BaseModel):
    id: int
    received_at: datetime
    category: str | None
    injection_flags: list[str]
    from_addr: str  # đã bọc untrusted
    subject: str  # đã bọc untrusted
    snippet: str  # đã bọc untrusted


class EmailDetail(EmailListItem):
    body: str  # đã bọc untrusted
    summary: str


class DraftOut(BaseModel):
    id: int
    to: list[str]
    subject: str
    body: str
    status: str
    reply_to_email_id: int | None
    pii_warnings: list[str]

    @classmethod
    def of(cls, d: EmailDraft) -> DraftOut:
        return cls(id=d.id, to=d.to_addrs.split(","), subject=d.subject, body=d.body, status=d.status,
                   reply_to_email_id=d.reply_to_email_id, pii_warnings=d.pii_warnings)


class SyncResult(BaseModel):
    fetched: int
    new: int
    flagged: list[int]  # id các email mới có dấu hiệu prompt injection


class EmailService:
    def __init__(self, session: Session, provider: EmailProvider, now: Callable[[], datetime] = now_vn) -> None:
        self.s = session
        self.provider = provider
        self.now = now

    def sync_inbox(self, max_results: int = 20) -> SyncResult:
        raw = self.provider.fetch_recent(max_results)
        ids = [r.provider_id for r in raw]
        known = set(self.s.scalars(select(Email.provider_id).where(Email.provider_id.in_(ids))))
        new, flagged = 0, []
        for r in raw:
            if r.provider_id in known:
                continue
            flags = detect_injection(f"{r.subject}\n{r.body}")
            e = Email(provider_id=r.provider_id, thread_id=r.thread_id, message_id_header=r.message_id_header,
                      from_addr=r.from_addr, to_addrs=r.to_addrs, subject=r.subject, body=r.body,
                      received_at=r.received_at, injection_flags=flags)
            self.s.add(e)
            self.s.flush()
            new += 1
            if flags:
                flagged.append(e.id)
        return SyncResult(fetched=len(raw), new=new, flagged=flagged)

    def list_emails(self, limit: int = 20, category: str | None = None,
                    since: datetime | None = None) -> list[EmailListItem]:
        q = select(Email).order_by(Email.received_at.desc()).limit(limit)
        if category:
            q = q.where(Email.category == category)
        if since:
            q = q.where(Email.received_at >= since)
        return [self._item(e) for e in self.s.scalars(q)]

    def get_email(self, email_id: int) -> EmailDetail:
        e = self._get(email_id)
        return EmailDetail(**self._item(e).model_dump(), body=wrap_untrusted(e.body[:8000], f"email#{e.id}.body"),
                           summary=e.summary)

    def label_email(self, email_id: int, category: str, summary: str = "") -> EmailListItem:
        if category not in CATEGORIES:
            raise EmailError(f"category phải là một trong {CATEGORIES}")
        e = self._get(email_id)
        e.category = category
        if summary:
            e.summary = summary[:1000]
        return self._item(e)

    def create_draft(self, to: list[str], subject: str, body: str, reply_to_email_id: int | None = None) -> DraftOut:
        bad = [a for a in to if not _EMAIL_ADDR.match(a.strip())]
        if not to or bad:
            raise EmailError(f"Địa chỉ người nhận không hợp lệ: {bad or 'trống'}")
        if reply_to_email_id is not None:
            self._get(reply_to_email_id)
        d = EmailDraft(to_addrs=",".join(a.strip() for a in to), subject=subject.strip(), body=body,
                       reply_to_email_id=reply_to_email_id, pii_warnings=scan_pii(f"{subject}\n{body}"))
        self.s.add(d)
        self.s.flush()
        return DraftOut.of(d)

    def list_drafts(self, status: str | None = "draft") -> list[DraftOut]:
        q = select(EmailDraft).order_by(EmailDraft.created_at.desc())
        if status:
            q = q.where(EmailDraft.status == status)
        return [DraftOut.of(d) for d in self.s.scalars(q)]

    def get_draft(self, draft_id: int) -> DraftOut:
        return DraftOut.of(self._get_draft(draft_id))

    def send_draft(self, draft_id: int) -> DraftOut:
        """Gửi đúng bản nháp đã lưu. Chỉ được gọi qua luồng duyệt (policy: send_email luôn cần duyệt)."""
        d = self._get_draft(draft_id)
        if d.status != "draft":
            raise EmailError(f"Bản nháp #{draft_id} đang ở trạng thái '{d.status}', không gửi được.")
        reply = self.s.get(Email, d.reply_to_email_id) if d.reply_to_email_id else None
        d.provider_message_id = self.provider.send(
            d.to_addrs.split(","), d.subject, d.body,
            thread_id=reply.thread_id if reply else None, in_reply_to=reply.message_id_header if reply else None)
        d.status, d.sent_at = "sent", self.now().replace(tzinfo=None)
        return DraftOut.of(d)

    def discard_draft(self, draft_id: int) -> DraftOut:
        d = self._get_draft(draft_id)
        d.status = "discarded"
        return DraftOut.of(d)

    # ---------- nội bộ ----------

    def _item(self, e: Email) -> EmailListItem:
        src = f"email#{e.id}"
        return EmailListItem(
            id=e.id, received_at=e.received_at, category=e.category, injection_flags=e.injection_flags,
            from_addr=wrap_untrusted(e.from_addr, f"{src}.from"), subject=wrap_untrusted(e.subject, f"{src}.subject"),
            snippet=wrap_untrusted(" ".join(e.body.split())[:300], f"{src}.snippet"),
        )

    def _get(self, email_id: int) -> Email:
        e = self.s.get(Email, email_id)
        if e is None:
            raise EmailError(f"Không có email #{email_id}.")
        return e

    def _get_draft(self, draft_id: int) -> EmailDraft:
        d = self.s.get(EmailDraft, draft_id)
        if d is None:
            raise EmailError(f"Không có bản nháp #{draft_id}.")
        return d
