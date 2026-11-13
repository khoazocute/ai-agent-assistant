"""Gửi tin CHỦ ĐỘNG cho người dùng (bản tin, nhắc lịch, cảnh báo) — có giờ yên lặng.

Tin chủ động khác tin trả lời: người dùng không hỏi mà vẫn nhận → phải tôn trọng giờ ngủ.
Giờ yên lặng 22:30–06:30: tin thường bị bỏ (ghi log); tin `urgent=True` (cảnh báo hệ thống) vẫn gửi.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, time
from typing import Protocol

from app.config import now_vn

log = logging.getLogger(__name__)
QUIET_START, QUIET_END = time(22, 30), time(6, 30)


def in_quiet_hours(now: datetime) -> bool:
    t = now.time()
    return t >= QUIET_START or t < QUIET_END


class Notifier(Protocol):
    async def send(self, text: str, urgent: bool = False) -> bool: ...


class LogNotifier:
    """Không có Telegram → ghi log (và giữ lại để test kiểm tra)."""

    def __init__(self, now: Callable[[], datetime] = now_vn) -> None:
        self.sent: list[str] = []
        self.now = now

    async def send(self, text: str, urgent: bool = False) -> bool:
        if in_quiet_hours(self.now()) and not urgent:
            log.info("Giờ yên lặng — bỏ tin: %s", text[:80])
            return False
        self.sent.append(text)
        log.info("Thông báo: %s", text[:200])
        return True


class TelegramNotifier:
    def __init__(self, token: str, chat_ids: set[int], now: Callable[[], datetime] = now_vn) -> None:
        self.token = token
        self.chat_ids = chat_ids
        self.now = now

    async def send(self, text: str, urgent: bool = False) -> bool:
        if in_quiet_hours(self.now()) and not urgent:
            log.info("Giờ yên lặng — bỏ tin Telegram")
            return False
        from telegram import Bot
        from telegram.constants import ParseMode

        from app.integrations.telegram_bot import md_to_html, truncate

        async with Bot(self.token) as bot:
            for chat_id in self.chat_ids:  # model hay trả **đậm** → HTML an toàn (escape trước khi định dạng)
                await bot.send_message(chat_id, truncate(md_to_html(text)), parse_mode=ParseMode.HTML)
        return True


def default_notifier() -> Notifier:
    from app.config import get_settings

    s = get_settings()
    if s.telegram_bot_token and s.allowed_chat_ids:
        return TelegramNotifier(s.telegram_bot_token, s.allowed_chat_ids)
    return LogNotifier()
