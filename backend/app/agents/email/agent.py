"""Email Agent = prompt.md + bộ tool email + vòng ReAct dùng chung."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.agents.base import BaseAgent, ExecutorFactory
from app.agents.email.tools import build_email_tools
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.context.prompts import load_prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.tools.executor import ToolExecutor
from app.integrations.email_provider import EmailProvider

PROMPT_PATH = Path(__file__).with_name("prompt.md")


class EmailAgent(BaseAgent):
    name = "email"
    max_steps = 10  # đọc nhiều thư + phân loại từng thư

    def __init__(self, llm: LLMClient, session_factory: SessionFactory, provider: EmailProvider,
                 now: Callable[[], datetime] = now_vn, make_executor: ExecutorFactory = ToolExecutor) -> None:
        super().__init__(llm, load_prompt(PROMPT_PATH), build_email_tools(session_factory, provider, now),
                         make_executor, now)
