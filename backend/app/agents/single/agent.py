"""Single-agent = prompt chung + prompt Finance + Schedule + Email, toàn bộ tool của ba agent."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from app.agents.base import BaseAgent, ExecutorFactory
from app.agents.email.agent import PROMPT_PATH as EMAIL_PROMPT
from app.agents.email.tools import build_email_tools
from app.agents.finance.agent import PROMPT_PATH as FINANCE_PROMPT
from app.agents.finance.tools import build_finance_tools
from app.agents.memory_tools import build_memory_tools
from app.agents.schedule.agent import PROMPT_PATH as SCHEDULE_PROMPT
from app.agents.schedule.tools import build_schedule_tools
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.context.prompts import compose_prompts, load_prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import ToolRegistry
from app.integrations.email_provider import EmailProvider

PROMPT_PATH = Path(__file__).with_name("prompt.md")


class SingleAgent(BaseAgent):
    name = "single"
    max_steps = 14  # một tin nhắn có thể cần tool của nhiều mảng

    def __init__(self, llm: LLMClient, session_factory: SessionFactory, email_provider: EmailProvider,
                 now: Callable[[], datetime] = now_vn, make_executor: ExecutorFactory = ToolExecutor) -> None:
        def today() -> date:
            return now().date()

        prompt = compose_prompts(load_prompt(PROMPT_PATH), load_prompt(FINANCE_PROMPT), load_prompt(SCHEDULE_PROMPT),
                                 load_prompt(EMAIL_PROMPT))
        registry = ToolRegistry.merge(build_finance_tools(session_factory, today),
                                      build_schedule_tools(session_factory, now),
                                      build_email_tools(session_factory, email_provider, now),
                                      build_memory_tools(session_factory))
        super().__init__(llm, prompt, registry, make_executor, now)
