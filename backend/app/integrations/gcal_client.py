"""GoogleCalendarProvider — Calendar API v3 (cần `pip install -e "backend[google]"` + đăng nhập Google).

Đồng bộ tăng dần bằng syncToken: lần đầu kéo 30 ngày gần đây + tương lai, các lần sau chỉ kéo phần thay đổi.
Sự kiện cả ngày (không có giờ) được bỏ qua — planner làm việc với khung giờ cụ thể.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.config import VN_TZ
from app.integrations.calendar_provider import RemoteEvent, SyncTokenExpired

TZ_NAME = "Asia/Ho_Chi_Minh"


class GoogleCalendarProvider:
    def __init__(self, credentials: Any, calendar_id: str = "primary") -> None:
        from googleapiclient.discovery import build

        self._events = build("calendar", "v3", credentials=credentials, cache_discovery=False).events()
        self.calendar_id = calendar_id

    def list_changes(self, sync_token: str | None) -> tuple[list[RemoteEvent], str]:
        from googleapiclient.errors import HttpError

        params: dict[str, Any] = {"calendarId": self.calendar_id, "singleEvents": True, "showDeleted": True,
                                  "maxResults": 250}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            params["timeMin"] = (datetime.now(VN_TZ) - timedelta(days=30)).isoformat()
        changes: list[RemoteEvent] = []
        while True:
            try:
                page = self._events.list(**params).execute()
            except HttpError as e:
                if e.resp.status == 410:
                    raise SyncTokenExpired() from e
                raise
            changes += [ev for item in page.get("items", []) if (ev := _to_remote(item)) is not None]
            if "nextPageToken" in page:
                params["pageToken"] = page["nextPageToken"]
                continue
            return changes, page["nextSyncToken"]

    def insert(self, title: str, start: datetime, end: datetime, location: str = "", note: str = "") -> RemoteEvent:
        body = _body(title, start, end, location, note)
        return _to_remote(self._events.insert(calendarId=self.calendar_id, body=body).execute())

    def update(self, event_id: str, title: str, start: datetime, end: datetime, location: str = "",
               note: str = "") -> RemoteEvent:
        body = _body(title, start, end, location, note)
        return _to_remote(self._events.patch(calendarId=self.calendar_id, eventId=event_id, body=body).execute())

    def delete(self, event_id: str) -> None:
        from googleapiclient.errors import HttpError

        try:
            self._events.delete(calendarId=self.calendar_id, eventId=event_id).execute()
        except HttpError as e:
            if e.resp.status not in (404, 410):  # đã bị xoá bên Google rồi → coi như xong
                raise


def _body(title: str, start: datetime, end: datetime, location: str, note: str) -> dict[str, Any]:
    return {"summary": title, "location": location, "description": note,
            "start": {"dateTime": start.isoformat(timespec="seconds"), "timeZone": TZ_NAME},
            "end": {"dateTime": end.isoformat(timespec="seconds"), "timeZone": TZ_NAME}}


def _to_remote(item: dict[str, Any]) -> RemoteEvent | None:
    cancelled = item.get("status") == "cancelled"
    start, end = item.get("start", {}).get("dateTime"), item.get("end", {}).get("dateTime")
    if not cancelled and not (start and end):
        return None  # sự kiện cả ngày
    return RemoteEvent(
        id=item["id"], title=item.get("summary", "(không tên)"),
        start=_to_local(start) if start else datetime.min, end=_to_local(end) if end else datetime.min,
        etag=item.get("etag", ""), location=item.get("location", ""), note=item.get("description", ""),
        cancelled=cancelled,
    )


def _to_local(rfc3339: str) -> datetime:
    """'2026-11-14T08:00:00Z' hoặc '...+07:00' → giờ VN không kèm múi giờ (cách lưu trong DB)."""
    return datetime.fromisoformat(rfc3339).astimezone(VN_TZ).replace(tzinfo=None)
