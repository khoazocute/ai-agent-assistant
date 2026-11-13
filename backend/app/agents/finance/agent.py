"""Finance Agent = prompt.md + bộ tool tài chính + vòng ReAct dùng chung."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from app.agents.base import BaseAgent, ExecutorFactory
from app.agents.finance.tools import build_finance_tools
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.context.prompts import load_prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.tools.executor import ToolExecutor

PROMPT_PATH = Path(__file__).with_name("prompt.md")


class FinanceAgent(BaseAgent):
    name = "finance"
    max_steps = 8  # ghi ~5 khoản trong 1 câu + trả lời vẫn đủ

    def __init__(self, llm: LLMClient, session_factory: SessionFactory, now: Callable[[], datetime] = now_vn,
                 make_executor: ExecutorFactory = ToolExecutor) -> None:
        def today() -> date:  # tool và agent dùng CHUNG một "bây giờ" → không lệch ngày khi test
            return now().date()

        registry = build_finance_tools(session_factory, today)
        super().__init__(llm, load_prompt(PROMPT_PATH), registry, make_executor, now)
