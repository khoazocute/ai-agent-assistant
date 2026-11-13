"""Giao diện lịch bên ngoài (Google Calendar) + bản giả cho test. Service đồng bộ không biết là Google hay giả."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class RemoteEvent:
    id: str
    title: str
    start: datetime  # giờ VN không kèm múi giờ
    end: datetime
    etag: str = ""
    location: str = ""
    note: str = ""
    cancelled: bool = False


class SyncTokenExpired(Exception):
    """Google trả 410 GONE: syncToken quá cũ → phải đồng bộ đầy đủ lại."""


class CalendarProvider(Protocol):
    def list_changes(self, sync_token: str | None) -> tuple[list[RemoteEvent], str]: ...

    def insert(self, title: str, start: datetime, end: datetime, location: str = "", note: str = "") -> RemoteEvent: ...

    def update(self, event_id: str, title: str, start: datetime, end: datetime, location: str = "",
               note: str = "") -> RemoteEvent: ...

    def delete(self, event_id: str) -> None: ...


@dataclass
class FakeCalendarProvider:
    """Mô phỏng Google: mỗi thay đổi có số thứ tự; syncToken = số thứ tự cuối cùng đã thấy."""

    events: dict[str, RemoteEvent] = field(default_factory=dict)
    changelog: list[tuple[int, str]] = field(default_factory=list)
    _seq: itertools.count = field(default_factory=lambda: itertools.count(1))
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def _touch(self, event_id: str) -> None:
        self.changelog.append((next(self._seq), event_id))

    def list_changes(self, sync_token: str | None) -> tuple[list[RemoteEvent], str]:
        since = int(sync_token or 0)
        changed_ids = list(dict.fromkeys(eid for seq, eid in self.changelog if seq > since))
        latest = str(self.changelog[-1][0]) if self.changelog else "0"
        return [self.events[eid] for eid in changed_ids], latest

    def insert(self, title, start, end, location="", note="") -> RemoteEvent:  # noqa: ANN001
        ev = RemoteEvent(f"g{next(self._ids)}", title, start, end, "e1", location, note)
        self.events[ev.id] = ev
        self._touch(ev.id)
        return ev

    def update(self, event_id, title, start, end, location="", note="") -> RemoteEvent:  # noqa: ANN001
        old = self.events[event_id]
        ev = RemoteEvent(event_id, title, start, end, f"e{int(old.etag[1:]) + 1}", location, note)
        self.events[event_id] = ev
        self._touch(event_id)
        return ev

    def delete(self, event_id: str) -> None:
        self.events[event_id].cancelled = True
        self._touch(event_id)

    # tiện cho test: thay đổi "do người dùng sửa trên Google"
    def remote_edit(self, event_id: str, **changes: object) -> None:
        ev = self.events[event_id]
        for k, v in changes.items():
            setattr(ev, k, v)
        ev.etag = f"e{int(ev.etag[1:]) + 1}"
        self._touch(event_id)
