"""Schedule Agent = prompt.md + bộ tool lịch + vòng ReAct dùng chung."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.agents.base import BaseAgent, ExecutorFactory
from app.agents.schedule.tools import build_schedule_tools
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.context.prompts import load_prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.tools.executor import ToolExecutor

PROMPT_PATH = Path(__file__).with_name("prompt.md")


class ScheduleAgent(BaseAgent):
    name = "schedule"
    max_steps = 8

    def __init__(self, llm: LLMClient, session_factory: SessionFactory, now: Callable[[], datetime] = now_vn,
                 make_executor: ExecutorFactory = ToolExecutor) -> None:
        super().__init__(llm, load_prompt(PROMPT_PATH), build_schedule_tools(session_factory, now), make_executor, now)
