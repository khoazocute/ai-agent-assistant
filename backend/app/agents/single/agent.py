"""Single-agent = prompt chung + prompt Finance + prompt Schedule, toàn bộ tool của hai agent."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from app.agents.base import BaseAgent, ExecutorFactory
from app.agents.finance.agent import PROMPT_PATH as FINANCE_PROMPT
from app.agents.finance.tools import build_finance_tools
from app.agents.schedule.agent import PROMPT_PATH as SCHEDULE_PROMPT
from app.agents.schedule.tools import build_schedule_tools
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.context.prompts import compose_prompts, load_prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import ToolRegistry

PROMPT_PATH = Path(__file__).with_name("prompt.md")


class SingleAgent(BaseAgent):
    name = "single"
    max_steps = 12  # một tin nhắn có thể cần tool của cả hai mảng

    def __init__(self, llm: LLMClient, session_factory: SessionFactory, now: Callable[[], datetime] = now_vn,
                 make_executor: ExecutorFactory = ToolExecutor) -> None:
        def today() -> date:
            return now().date()

        prompt = compose_prompts(load_prompt(PROMPT_PATH), load_prompt(FINANCE_PROMPT), load_prompt(SCHEDULE_PROMPT))
        registry = ToolRegistry.merge(build_finance_tools(session_factory, today),
                                      build_schedule_tools(session_factory, now))
        super().__init__(llm, prompt, registry, make_executor, now)
