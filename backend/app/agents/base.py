"""BaseAgent — mọi agent = prompt.md + bộ tool riêng + vòng ReAct dùng chung.

Agent con chỉ khai báo: tên, đường dẫn prompt, cách dựng ToolRegistry. Phần còn lại (chèn thời điểm,
gắn version prompt vào trace, gọi run_react) giống hệt nhau → viết một lần ở đây.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.config import now_vn
from app.harness.agentops.tracer import Tracer
from app.harness.context.prompts import Prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.orchestration.react_loop import RunResult, run_react
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import ToolRegistry

ExecutorFactory = Callable[[ToolRegistry], ToolExecutor]
WEEKDAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def time_header(now: datetime) -> str:
    return f"[Thời điểm hiện tại: {WEEKDAYS_VI[now.weekday()]} {now:%d/%m/%Y %H:%M}, giờ Việt Nam]"


class BaseAgent:
    name = "base"
    max_steps = 8

    def __init__(self, llm: LLMClient, prompt: Prompt, registry: ToolRegistry,
                 make_executor: ExecutorFactory = ToolExecutor, now: Callable[[], datetime] = now_vn) -> None:
        self.llm = llm
        self.prompt = prompt
        self.now = now
        self.registry = registry
        # Hàm tạo executor (không phải executor dựng sẵn): bước 11 truyền vào executor có policy + duyệt.
        self.executor = make_executor(registry)
        self.executor.agent_name = self.name

    def run(self, user_text: str, tracer: Tracer | None = None, history: list[tuple[str, str]] | None = None,
            meta: dict[str, Any] | None = None) -> RunResult:
        return run_react(
            self.llm, self.prompt.text, self.with_time(user_text), self.executor,
            max_steps=self.max_steps, tracer=tracer, history=history,
            meta={"agent": self.name, "prompt_version": self.prompt.version, **(meta or {})},
        )

    def with_time(self, user_text: str) -> str:
        # Thời điểm đặt trong USER message, không đặt trong system prompt: system giữ nguyên giữa các
        # lần gọi (tốt cho prompt cache, version prompt ổn định), còn thời gian thì luôn mới.
        return f"{time_header(self.now())}\n{user_text}"
