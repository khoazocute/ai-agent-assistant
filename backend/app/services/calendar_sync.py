"""Đồng bộ HAI CHIỀU lịch trong DB ↔ Google Calendar (ADR-0013).

Một lượt sync = ĐẨY rồi KÉO:
  đẩy  - sự kiện local chưa có gcal_event_id         → tạo trên Google
       - sự kiện đã sửa ở local (synced_at = NULL, do ScheduleService đặt) → cập nhật trên Google
       - sự kiện đã xoá ở local (tombstone)          → xoá trên Google
  kéo  - thay đổi trên Google kể từ syncToken trước → tạo/cập nhật/xoá ở local
Xung đột (cùng sửa ở hai nơi giữa hai lượt sync): đẩy chạy TRƯỚC nên bản local được ghi lên Google, rồi kéo
nhận lại chính bản đó — "local thắng". Đơn giản, dễ đoán, đủ cho một người dùng.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import now_vn
from app.db.models import CalendarTombstone, Event, SyncState
from app.integrations.calendar_provider import CalendarProvider, RemoteEvent, SyncTokenExpired

TOKEN_KEY = "gcal_sync_token"


class SyncReport(BaseModel):
    pushed_new: int = 0
    pushed_updates: int = 0
    pushed_deletes: int = 0
    pulled_new: int = 0
    pulled_updates: int = 0
    pulled_deletes: int = 0
    full_resync: bool = False


class CalendarSync:
    def __init__(self, session: Session, provider: CalendarProvider,
                 now: Callable[[], datetime] = now_vn) -> None:
        self.s = session
        self.provider = provider
        self.now = lambda: now().replace(tzinfo=None)

    def run(self) -> SyncReport:
        report = SyncReport()
        self._push(report)
        self._pull(report)
        return report

    # ---------- đẩy ----------

    def _push(self, report: SyncReport) -> None:
        for tomb in list(self.s.scalars(select(CalendarTombstone))):
            self.provider.delete(tomb.gcal_event_id)
            self.s.delete(tomb)
            report.pushed_deletes += 1
        for e in self.s.scalars(select(Event)):
            if e.gcal_event_id is None:
                remote = self.provider.insert(e.title, e.start_at, e.end_at, e.location, e.note)
                e.gcal_event_id = remote.id
                report.pushed_new += 1
            elif e.synced_at is None:
                remote = self.provider.update(e.gcal_event_id, e.title, e.start_at, e.end_at, e.location, e.note)
                report.pushed_updates += 1
            else:
                continue
            self._mark_synced(e, remote.etag)
        self.s.flush()

    # ---------- kéo ----------

    def _pull(self, report: SyncReport) -> None:
        state = self.s.get(SyncState, TOKEN_KEY)
        try:
            changes, token = self.provider.list_changes(state.value if state else None)
        except SyncTokenExpired:
            report.full_resync = True
            changes, token = self.provider.list_changes(None)
        by_gcal = {e.gcal_event_id: e for e in self.s.scalars(select(Event).where(Event.gcal_event_id.is_not(None)))}
        for remote in changes:
            local = by_gcal.get(remote.id)
            if remote.cancelled:
                if local is not None:
                    self.s.delete(local)
                    report.pulled_deletes += 1
                continue
            if local is None:
                local = Event(title=remote.title, start_at=remote.start, end_at=remote.end, location=remote.location,
                              note=remote.note, source="gcal", gcal_event_id=remote.id)
                self.s.add(local)
                report.pulled_new += 1
            elif local.etag == remote.etag:
                continue  # chính thay đổi mình vừa đẩy lên → bỏ qua
            else:
                self._apply(local, remote)
                report.pulled_updates += 1
            self._mark_synced(local, remote.etag)
        if state is None:
            self.s.add(SyncState(key=TOKEN_KEY, value=token))
        else:
            state.value = token
        self.s.flush()

    def _apply(self, local: Event, remote: RemoteEvent) -> None:
        local.title, local.start_at, local.end_at = remote.title, remote.start, remote.end
        local.location, local.note = remote.location, remote.note

    def _mark_synced(self, e: Event, etag: str) -> None:
        # Tín hiệu "cần đẩy" là synced_at = NULL (tường minh), KHÔNG so updated_at > synced_at: updated_at có
        # onupdate tự đặt giờ, so thời gian dễ sai (cùng giây, gán lại giá trị cũ…) → đẩy ngược ghi đè Google.
        e.etag, e.synced_at = etag, self.now()
