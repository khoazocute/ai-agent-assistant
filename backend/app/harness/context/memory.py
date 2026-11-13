"""Memory — agent "nhớ" được gì giữa các tin nhắn (ADR-0011).

Ngắn hạn  conversations + conversation_messages: các lượt hỏi–đáp gần nhất theo từng cuộc trò chuyện
          (chat Telegram, phiên web). Chỉ lưu CHỮ của người dùng và câu trả lời cuối — không lưu tool call
          cũ: đủ để hiểu "dời nó sang 3h", rẻ token, và không mang theo nội dung email không tin cậy.
Dài hạn   user_facts: điều người dùng muốn trợ lý nhớ lâu ("tôi ngủ lúc 23h", "sếp tên Minh").
          Agent đọc qua tool `recall_facts` khi cần — KHÔNG tự nhét vào mọi prompt (tiết kiệm token,
          và người dùng kiểm soát được điều gì được nhớ).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, delete, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.harness.storage import HarnessBase

_VN = timezone(timedelta(hours=7))


def _now() -> datetime:
    return datetime.now(_VN).replace(tzinfo=None)


class Conversation(HarnessBase):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("channel", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(20))  # telegram | web | cli
    external_id: Mapped[str] = mapped_column(String(100))  # chat_id Telegram, id phiên web
    created_at: Mapped[datetime] = mapped_column(default=_now)


class ConversationMessage(HarnessBase):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | assistant
    text: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(default=_now)


class UserFact(HarnessBase):
    __tablename__ = "user_facts"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


class ConversationMemory:
    def __init__(self, session_factory: sessionmaker, max_turns: int = 6, max_age_hours: float = 12) -> None:
        self.factory = session_factory
        self.max_turns = max_turns
        # Cuộc trò chuyện ngắt quãng lâu (hôm qua) thường là chủ đề mới → không kéo ngữ cảnh cũ vào.
        self.max_age = timedelta(hours=max_age_hours)

    def conversation_id(self, channel: str, external_id: str) -> int:
        with self.factory() as s, s.begin():
            conv = s.scalars(select(Conversation).where(Conversation.channel == channel,
                                                        Conversation.external_id == external_id)).first()
            if conv is None:
                conv = Conversation(channel=channel, external_id=external_id)
                s.add(conv)
                s.flush()
            return conv.id

    def recent(self, conversation_id: int) -> list[tuple[str, str]]:
        with self.factory() as s:
            rows = list(s.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id,
                       ConversationMessage.created_at >= _now() - self.max_age)
                .order_by(ConversationMessage.id.desc()).limit(self.max_turns)))
        return [(m.role, m.text) for m in reversed(rows)]

    def append(self, conversation_id: int, role: str, text: str, run_id: str = "") -> None:
        with self.factory() as s, s.begin():
            s.add(ConversationMessage(conversation_id=conversation_id, role=role, text=text[:4000], run_id=run_id))

    def reset(self, conversation_id: int) -> None:
        with self.factory() as s, s.begin():
            s.execute(delete(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id))


class UserFacts:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.factory = session_factory

    def remember(self, key: str, value: str) -> None:
        with self.factory() as s, s.begin():
            fact = s.get(UserFact, key.strip().lower())
            if fact is None:
                s.add(UserFact(key=key.strip().lower(), value=value.strip()))
            else:
                fact.value = value.strip()

    def forget(self, key: str) -> bool:
        with self.factory() as s, s.begin():
            fact = s.get(UserFact, key.strip().lower())
            if fact is not None:
                s.delete(fact)
            return fact is not None

    def all(self) -> dict[str, str]:
        with self.factory() as s:
            return {f.key: f.value for f in s.scalars(select(UserFact).order_by(UserFact.key))}
