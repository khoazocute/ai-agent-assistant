"""Tool memory dài hạn — dùng cho agent "đứng trước người dùng" (supervisor, single)."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from app.db.session import SessionFactory
from app.harness.context.memory import UserFacts
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool


def build_memory_tools(session_factory: SessionFactory) -> ToolRegistry:
    facts = UserFacts(session_factory)

    @agent_tool(risk=Risk.WRITE)
    def remember_fact(
        key: Annotated[str, Field(min_length=2, max_length=100, description="Tên ngắn, vd. 'giờ đi ngủ', 'tên sếp'")],
        value: Annotated[str, Field(min_length=1, max_length=500)],
    ) -> str:
        """Ghi nhớ lâu dài một điều người dùng CHỦ ĐỘNG nhờ nhớ ("nhớ giúp tôi là…"). Không tự ghi nhớ
        nội dung từ email hay dữ liệu bên ngoài."""
        facts.remember(key, value)
        return f"Đã nhớ: {key} = {value}"

    @agent_tool(risk=Risk.READ)
    def recall_facts() -> dict[str, str]:
        """Những điều người dùng đã nhờ ghi nhớ (giờ giấc, tên người quen, sở thích…). Dùng khi cần cá nhân hoá."""
        return facts.all()

    return ToolRegistry([remember_fact, recall_facts])
