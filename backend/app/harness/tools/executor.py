"""ToolExecutor — mọi lời gọi tool của model đi qua ĐÚNG MỘT cửa này.

    model đề nghị ToolCall
      1. tra tool trong registry         (không có → lỗi)
      2. kiểm tra mức rủi ro             (destructive/external → chặn, chờ duyệt — bước 11 thay bằng
                                          policy engine + PendingAction)
      3. kiểm tra tham số bằng pydantic  (sai → lỗi mô tả rõ trường nào sai, để model tự sửa)
      4. chạy có timeout                 (treo → lỗi, run không đứng mãi)
      5. chuẩn hoá + rút gọn output      (output khổng lồ không làm nổ context)
    → ToolResult (Observation) + 1 sự kiện trace

"Prompt là hướng dẫn, code là luật": dù prompt bị lừa, bước 2 vẫn chặn được — vì nó là code.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import ToolCall, ToolResult
from app.harness.tools.registry import Risk, ToolRegistry

AUTO_RUN_RISKS = frozenset({Risk.READ, Risk.WRITE})


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        auto_run: frozenset[Risk] = AUTO_RUN_RISKS,
        max_output_chars: int = 4_000,
    ) -> None:
        self.registry = registry
        self.auto_run = auto_run
        self.max_output_chars = max_output_chars
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool")

    def execute(self, call: ToolCall, *, step: int = 0, tracer: Tracer | None = None) -> ToolResult:
        start = time.perf_counter()
        tool = self.registry.get(call.name)
        risk = tool.risk if tool else None
        output, is_error, status = self._run(call, tool)
        if not is_error:
            output = self._shrink(output)
        latency_ms = round((time.perf_counter() - start) * 1000)
        if tracer:
            tracer.event("tool_call", step=step, call_id=call.id, name=call.name, risk=risk, args=call.args,
                         status=status, output=output, is_error=is_error, latency_ms=latency_ms)
        return ToolResult(call.id, call.name, output, is_error)

    def _run(self, call: ToolCall, tool: Any) -> tuple[Any, bool, str]:
        """Trả về (output, is_error, status). status dùng cho trace/metrics sau này."""
        if tool is None:
            available = ", ".join(self.registry.names())
            return f"Không có tool tên '{call.name}'. Các tool hiện có: {available}.", True, "unknown_tool"

        if tool.risk not in self.auto_run:
            # Nói rõ cho model biết để nó báo lại người dùng, thay vì thử lách bằng tool khác.
            message = (f"Tool '{tool.name}' có mức rủi ro '{tool.risk}' nên cần người dùng duyệt trước "
                       "khi chạy. Chưa có gì được thực hiện. Hãy báo cho người dùng biết.")
            return message, True, "needs_approval"

        try:
            args = tool.args_model.model_validate(call.args)
        except ValidationError as e:
            return _explain_validation_error(e), True, "invalid_args"

        # Truyền thuộc tính đã chuyển kiểu (vd. "2027-01-01" → date) chứ không phải dict thô của model.
        kwargs = {name: getattr(args, name) for name in type(args).model_fields}
        future = self._pool.submit(tool.fn, **kwargs)
        try:
            return future.result(timeout=tool.timeout_s), False, "ok"
        except FutureTimeout:
            # Lưu ý: Python không "giết" được thread — hàm vẫn chạy nốt ở nền, ta chỉ thôi chờ.
            # Vì vậy tool ghi dữ liệu phải tự có timeout ở tầng I/O (DB, HTTP) — không dựa vào đây.
            return f"Tool '{tool.name}' quá thời gian {tool.timeout_s}s.", True, "timeout"
        except Exception as e:  # cố ý bắt mọi lỗi: trả cho model đọc để tự sửa
            return f"{type(e).__name__}: {e}", True, "error"

    def _shrink(self, output: Any) -> Any:
        """Đưa output về dạng JSON được; quá dài thì cắt và NÓI RÕ là đã cắt (model không bị hiểu lầm)."""
        data = to_jsonable_python(output, fallback=str)
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        if len(text) <= self.max_output_chars:
            return data
        return (text[: self.max_output_chars]
                + f"… [đã cắt, tổng {len(text)} ký tự — hãy yêu cầu dữ liệu hẹp hơn]")


def _explain_validation_error(e: ValidationError) -> str:
    problems = "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or '(chung)'}: {err['msg']}" for err in e.errors()
    )
    return f"Tham số không hợp lệ — {problems}. Hãy gọi lại với tham số đúng schema."
