"""Giao diện nhà cung cấp email — service không biết đang nói chuyện với Gmail hay bản giả.

- GmailProvider (gmail_client.py)     dùng thật, cần OAuth
- FakeEmailProvider                   test + eval + demo: hộp thư trong RAM, "gửi" chỉ ghi lại
- NotConnectedEmailProvider           chưa kết nối Gmail → mọi thao tác báo lỗi rõ ràng (không âm thầm dùng bản giả)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class RawEmail:
    provider_id: str
    from_addr: str
    subject: str
    body: str
    received_at: datetime  # giờ VN không kèm múi giờ
    to_addrs: str = ""
    thread_id: str = ""
    message_id_header: str = ""  # header Message-ID — để trả lời đúng luồng


@dataclass
class SentEmail:
    to: list[str]
    subject: str
    body: str
    thread_id: str | None
    in_reply_to: str | None


class EmailProvider(Protocol):
    def fetch_recent(self, max_results: int = 20) -> list[RawEmail]: ...

    def send(self, to: list[str], subject: str, body: str, thread_id: str | None = None,
             in_reply_to: str | None = None) -> str: ...


class NotConnectedEmailProvider:
    MESSAGE = "Chưa kết nối Gmail. Chạy `python -m app.integrations.google_auth` để đăng nhập (xem README)."

    def fetch_recent(self, max_results: int = 20) -> list[RawEmail]:
        raise RuntimeError(self.MESSAGE)

    def send(self, to, subject, body, thread_id=None, in_reply_to=None) -> str:  # noqa: ANN001
        raise RuntimeError(self.MESSAGE)


@dataclass
class FakeEmailProvider:
    inbox: list[RawEmail] = field(default_factory=list)
    sent: list[SentEmail] = field(default_factory=list)

    def fetch_recent(self, max_results: int = 20) -> list[RawEmail]:
        return sorted(self.inbox, key=lambda e: e.received_at, reverse=True)[:max_results]

    def send(self, to: list[str], subject: str, body: str, thread_id: str | None = None,
             in_reply_to: str | None = None) -> str:
        self.sent.append(SentEmail(to, subject, body, thread_id, in_reply_to))
        return f"fake-sent-{len(self.sent)}"
