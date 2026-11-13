"""GmailProvider — đọc hộp thư và gửi mail qua Gmail API (cần `pip install -e "backend[google]"` + đăng nhập).

Chỉ chuyển đổi định dạng Gmail ↔ RawEmail; không có nghiệp vụ (nghiệp vụ ở services/email_service.py).
"""

from __future__ import annotations

import base64
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any

from app.config import VN_TZ
from app.integrations.email_provider import RawEmail


class GmailProvider:
    def __init__(self, credentials: Any) -> None:
        from googleapiclient.discovery import build

        self._svc = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def fetch_recent(self, max_results: int = 20) -> list[RawEmail]:
        users = self._svc.users()
        listing = users.messages().list(userId="me", maxResults=max_results, q="in:inbox newer_than:7d").execute()
        emails = []
        for ref in listing.get("messages", []):
            msg = users.messages().get(userId="me", id=ref["id"], format="full").execute()
            emails.append(_to_raw(msg))
        return emails

    def send(self, to: list[str], subject: str, body: str, thread_id: str | None = None,
             in_reply_to: str | None = None) -> str:
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"] = ", ".join(to)
        mime["Subject"] = subject
        if in_reply_to:  # giữ đúng luồng hội thoại ở phía người nhận
            mime["In-Reply-To"] = in_reply_to
            mime["References"] = in_reply_to
        payload: dict[str, Any] = {"raw": base64.urlsafe_b64encode(mime.as_bytes()).decode()}
        if thread_id:
            payload["threadId"] = thread_id
        return self._svc.users().messages().send(userId="me", body=payload).execute()["id"]


def _to_raw(msg: dict[str, Any]) -> RawEmail:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    received = datetime.fromtimestamp(int(msg.get("internalDate", "0")) / 1000, VN_TZ).replace(tzinfo=None)
    return RawEmail(
        provider_id=msg["id"], thread_id=msg.get("threadId", ""), from_addr=headers.get("from", ""),
        to_addrs=headers.get("to", ""), subject=headers.get("subject", "(không tiêu đề)"),
        body=_plain_text(msg.get("payload", {})) or msg.get("snippet", ""), received_at=received,
        message_id_header=headers.get("message-id", ""),
    )


def _plain_text(part: dict[str, Any]) -> str:
    """Lấy phần text/plain đầu tiên (đệ quy qua multipart). Bỏ HTML — giảm bề mặt injection ẩn trong thẻ."""
    if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    for sub in part.get("parts", []) or []:
        text = _plain_text(sub)
        if text:
            return text
    return ""
