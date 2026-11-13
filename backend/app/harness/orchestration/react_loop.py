"""Vòng ReAct thủ công: Thought → Action → Observation, lặp tới khi model trả lời xong.

Tự viết thay vì dùng automatic function calling hay LangGraph (ADR-0003): mỗi bước đi qua code
của MÌNH, nên chèn được trace (bước 2), policy + duyệt (bước 11) vào giữa "model đề nghị" và
"tool thực sự chạy".

Bước 2 nhận tool dạng (ToolSpec, hàm Python) đơn giản; bước 3 thay bằng Tool Registry + Executor.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import LLMClient, ToolCall, ToolResult, ToolSpec, Usage

RunStatus = Literal["ok", "max_steps"]


@dataclass
class Tool:
    spec: ToolSpec
    fn: Callable[..., Any]


@dataclass
class RunResult:
    run_id: str
    status: RunStatus
    answer: str
    steps: int
    usage: Usage
    tool_calls: list[ToolCall] = field(default_factory=list)


def run_react(
    llm: LLMClient,
    system: str,
    user_input: str,
    tools: list[Tool],
    *,
    max_steps: int = 6,
    tracer: Tracer | None = None,
) -> RunResult:
    tracer = tracer or Tracer()  # không truyền → không ghi đâu cả
    by_name = {t.spec.name: t for t in tools}
    specs = [t.spec for t in tools]
    history: list[Any] = [llm.user_message(user_input)]
    usage = Usage()
    all_calls: list[ToolCall] = []

    tracer.event("run_start", model=llm.model, input=user_input, system=system, tools=specs,
                 max_steps=max_steps)

    for step in range(1, max_steps + 1):
        # Ghi CHÍNH XÁC thứ được gửi đi (system + tools đã có ở run_start).
        tracer.event("llm_request", step=step, history=history)
        resp = llm.generate(system, history, specs)
        usage += resp.usage
        tracer.event("llm_response", step=step, thoughts=resp.thoughts, text=resp.text,
                     tool_calls=resp.tool_calls, usage=resp.usage, finish_reason=resp.finish_reason,
                     latency_ms=resp.latency_ms)

        # Nối nguyên vẹn lượt của model vào lịch sử TRƯỚC khi thêm kết quả tool.
        history.append(resp.message)

        if not resp.tool_calls:  # không đề nghị Action nào → đây là câu trả lời cuối
            tracer.event("run_end", status="ok", answer=resp.text, steps=step, usage=usage)
            return RunResult(tracer.run_id, "ok", resp.text, step, usage, all_calls)

        all_calls.extend(resp.tool_calls)
        results = [_execute(call, by_name, step, tracer) for call in resp.tool_calls]
        history.append(llm.tool_results_message(results))

    # Chặn lặp vô hạn / tốn tiền vô hạn: hết số bước thì dừng, KHÔNG để model tự quyết.
    answer = "Xin lỗi, tôi chưa hoàn thành được yêu cầu trong giới hạn số bước cho phép."
    tracer.event("run_end", status="max_steps", answer=answer, steps=max_steps, usage=usage)
    return RunResult(tracer.run_id, "max_steps", answer, max_steps, usage, all_calls)


def _execute(call: ToolCall, by_name: dict[str, Tool], step: int, tracer: Tracer) -> ToolResult:
    """Chạy một tool. Mọi lỗi được biến thành Observation thay vì làm sập cả run."""
    start = time.perf_counter()
    tool = by_name.get(call.name)
    if tool is None:
        result = ToolResult(call.id, call.name, f"Không có tool tên '{call.name}'.", is_error=True)
    else:
        try:
            result = ToolResult(call.id, call.name, tool.fn(**call.args))
        except Exception as e:  # cố ý bắt mọi lỗi: trả cho model đọc để tự sửa
            result = ToolResult(call.id, call.name, f"{type(e).__name__}: {e}", is_error=True)
    latency_ms = round((time.perf_counter() - start) * 1000)
    tracer.event("tool_call", step=step, call_id=call.id, name=call.name, args=call.args,
                 output=result.output, is_error=result.is_error, latency_ms=latency_ms)
    return result
