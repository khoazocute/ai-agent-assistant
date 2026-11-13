"""Supervisor — multi-agent theo mẫu agent-as-tool (ADR-0008).

Mỗi sub-agent là MỘT tool của Supervisor (`ask_finance_agent(request)`…). Khi tool chạy:
  - sub-agent chạy vòng ReAct RIÊNG với prompt + bộ tool riêng (ngắn, chuyên)
  - trace của sub-agent là một run con (`parent_run_id`) → xem được cây Supervisor → sub-agent
  - Supervisor chỉ nhận câu trả lời cuối của sub-agent, không thấy chi tiết tool bên trong
Độ sâu ủy quyền = 1: sub-agent không có tool ask_* → không thể gọi vòng lại.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from app.agents.base import BaseAgent, ExecutorFactory
from app.agents.finance.agent import FinanceAgent
from app.agents.schedule.agent import ScheduleAgent
from app.config import now_vn
from app.db.session import SessionFactory
from app.harness.agentops.tracer import Tracer
from app.harness.context.prompts import load_prompt
from app.harness.orchestration.llm_client import LLMClient, ToolCall, Usage
from app.harness.orchestration.react_loop import RunResult
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool

PROMPT_PATH = Path(__file__).with_name("prompt.md")
RequestArg = Annotated[str, Field(min_length=3, max_length=2000,
                                  description="Yêu cầu tự đủ ý, giữ nguyên số tiền/mốc thời gian người dùng nói")]


class SupervisorAgent(BaseAgent):
    name = "supervisor"
    max_steps = 6

    def __init__(self, llm: LLMClient, session_factory: SessionFactory, now: Callable[[], datetime] = now_vn,
                 make_executor: ExecutorFactory = ToolExecutor) -> None:
        self.subs: dict[str, BaseAgent] = {
            "finance": FinanceAgent(llm, session_factory, now, make_executor),
            "schedule": ScheduleAgent(llm, session_factory, now, make_executor),
        }
        self._tracer: Tracer | None = None
        self._child_usage = Usage()
        self._child_calls: list[ToolCall] = []
        super().__init__(llm, load_prompt(PROMPT_PATH), self._build_tools(), make_executor, now)

    def _build_tools(self) -> ToolRegistry:
        # Sub-agent có thể chạy nhiều bước + retry khi Gemini quá tải → timeout dài hơn tool thường.
        @agent_tool(risk=Risk.READ, timeout_s=300)
        def ask_finance_agent(request: RequestArg) -> dict[str, Any]:
            """Giao việc thu chi cho Finance Agent: ghi khoản chi/thu, hỏi tổng tiền, chi ròng, xoá giao dịch."""
            return self._delegate("finance", request)

        @agent_tool(risk=Risk.READ, timeout_s=300)
        def ask_schedule_agent(request: RequestArg) -> dict[str, Any]:
            """Giao việc lịch cho Schedule Agent: tạo/dời/xem sự kiện, giờ trống, việc cần làm, xếp lịch."""
            return self._delegate("schedule", request)

        return ToolRegistry([ask_finance_agent, ask_schedule_agent])

    def _delegate(self, name: str, request: str) -> dict[str, Any]:
        tracer = self._tracer.child() if self._tracer else None
        result = self.subs[name].run(request, tracer)
        self._child_usage += result.usage
        self._child_calls.extend(result.tool_calls)
        return {"agent": name, "status": result.status, "answer": result.answer,
                "tools_used": [c.name for c in result.tool_calls]}

    def run(self, user_text: str, tracer: Tracer | None = None, history: list[tuple[str, str]] | None = None,
            meta: dict[str, Any] | None = None) -> RunResult:
        self._tracer = tracer
        self._child_usage, self._child_calls = Usage(), []
        result = super().run(user_text, tracer, history, meta)
        # Chi phí THẬT của một yêu cầu = Supervisor + mọi sub-agent → cộng lại để benchmark công bằng.
        result.usage = result.usage + self._child_usage
        result.tool_calls = result.tool_calls + self._child_calls
        return result
