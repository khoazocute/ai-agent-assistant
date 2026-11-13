"""Danh sách agent của app — một chỗ để CLI, Telegram, web, eval, benchmark dựng agent theo tên."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.agents.base import BaseAgent, ExecutorFactory
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.orchestration.llm_client import LLMClient
from app.harness.tools.executor import ToolExecutor

AGENT_NAMES = ("finance", "schedule")


def build_agent(name: str, llm: LLMClient, session_factory: SessionFactory, now: Callable[[], datetime] = now_vn,
                make_executor: ExecutorFactory = ToolExecutor) -> BaseAgent:
    if name == "finance":
        from app.agents.finance.agent import FinanceAgent

        return FinanceAgent(llm, session_factory, now, make_executor)
    if name == "schedule":
        from app.agents.schedule.agent import ScheduleAgent

        return ScheduleAgent(llm, session_factory, now, make_executor)
    raise ValueError(f"Không có agent '{name}'. Có: {', '.join(AGENT_NAMES)}")
