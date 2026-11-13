"""Finance Agent = prompt.md + bộ tool riêng + vòng ReAct dùng chung."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from app.agents.finance.tools import build_finance_tools
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.agentops.tracer import Tracer
from app.harness.context.prompts import load_prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.orchestration.react_loop import RunResult, run_react
from app.harness.tools.executor import ToolExecutor

PROMPT_PATH = Path(__file__).with_name("prompt.md")
WEEKDAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


class FinanceAgent:
    name = "finance"
    max_steps = 8  # ghi ~5 khoản trong 1 câu + trả lời vẫn đủ

    def __init__(self, llm: LLMClient, session_factory: SessionFactory,
                 now: Callable[[], datetime] = now_vn) -> None:
        self.llm = llm
        self.now = now
        self.prompt = load_prompt(PROMPT_PATH)
        def today() -> date:  # tool và agent dùng CHUNG một "bây giờ" → không lệch ngày khi test
            return now().date()

        self.executor = ToolExecutor(build_finance_tools(session_factory, today))

    def run(self, user_text: str, tracer: Tracer | None = None) -> RunResult:
        return run_react(
            self.llm, self.prompt.text, self._with_time(user_text), self.executor,
            max_steps=self.max_steps, tracer=tracer,
            meta={"agent": self.name, "prompt_version": self.prompt.version},
        )

    def _with_time(self, user_text: str) -> str:
        # Thời điểm đặt trong USER message, không đặt trong system prompt: system giữ nguyên giữa các
        # lần gọi (tốt cho prompt cache, version prompt ổn định), còn thời gian thì luôn mới.
        n = self.now()
        return f"[Thời điểm hiện tại: {WEEKDAYS_VI[n.weekday()]} {n:%d/%m/%Y %H:%M}, giờ Việt Nam]\n{user_text}"
