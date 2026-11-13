"""Vòng ReAct thủ công: Thought → Action → Observation, lặp tới khi model trả lời xong.

Tự viết thay vì dùng automatic function calling hay LangGraph (ADR-0003): mỗi bước đi qua code
của MÌNH, nên chèn được trace (bước 2), kiểm tra tham số + mức rủi ro (bước 3, ToolExecutor),
policy + duyệt (bước 11) vào giữa "model đề nghị" và "tool thực sự chạy".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import LLMClient, ToolCall, Usage

if TYPE_CHECKING:  # chỉ cần cho type hint; tránh import vòng tools ↔ orchestration lúc chạy
    from app.harness.tools.executor import ToolExecutor

RunStatus = Literal["ok", "max_steps"]  # lỗi LLM → exception (trace ghi run_end status="error")


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
    executor: ToolExecutor,
    *,
    max_steps: int = 6,
    tracer: Tracer | None = None,
    meta: dict[str, Any] | None = None,
) -> RunResult:
    """`meta`: thông tin thêm ghi vào run_start (vd. agent, prompt_version) — để biết run dùng prompt nào."""
    tracer = tracer or Tracer()  # không truyền → không ghi đâu cả
    specs = executor.registry.specs()
    history: list[Any] = [llm.user_message(user_input)]
    usage = Usage()
    all_calls: list[ToolCall] = []

    tracer.event("run_start", **(meta or {}), model=llm.model, input=user_input, system=system, tools=specs,
                 max_steps=max_steps)

    for step in range(1, max_steps + 1):
        # Ghi CHÍNH XÁC thứ được gửi đi (system + tools đã có ở run_start).
        tracer.event("llm_request", step=step, history=history)
        try:
            resp = llm.generate(system, history, specs)
        except Exception as e:
            # Lỗi API sau khi đã retry (hết quota, 5xx kéo dài…): vẫn đóng run trong trace rồi mới ném lỗi
            # lên — nếu không, trace có run_start mà không có run_end, không biết run đã chết ở đâu.
            tracer.event("run_end", status="error", error=f"{type(e).__name__}: {e}", steps=step, usage=usage)
            raise
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
        results = [executor.execute(call, step=step, tracer=tracer) for call in resp.tool_calls]
        history.append(llm.tool_results_message(results))

    # Chặn lặp vô hạn / tốn tiền vô hạn: hết số bước thì dừng, KHÔNG để model tự quyết.
    answer = "Xin lỗi, tôi chưa hoàn thành được yêu cầu trong giới hạn số bước cho phép."
    tracer.event("run_end", status="max_steps", answer=answer, steps=max_steps, usage=usage)
    return RunResult(tracer.run_id, "max_steps", answer, max_steps, usage, all_calls)
