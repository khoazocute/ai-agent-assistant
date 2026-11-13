"""ToolExecutor — mọi lời gọi tool của model đi qua ĐÚNG MỘT cửa này.

    model đề nghị ToolCall
      1. tra tool trong registry          (không có → lỗi)
      2. kiểm tra tham số bằng pydantic   (sai → lỗi chỉ rõ trường sai, để model tự sửa)
      3. hỏi policy (bước 11)             allow → chạy · require_approval → tạo PendingAction · deny → từ chối
         (không cấu hình policy → luật mặc định: chỉ read/write chạy ngay)
      4. chạy có timeout                  (treo → lỗi, run không đứng mãi)
      5. chuẩn hoá + rút gọn output       (output khổng lồ không làm nổ context)
      6. audit (tool ghi/xoá/gửi)         + 1 sự kiện trace
    → ToolResult (Observation)

"Prompt là hướng dẫn, code là luật": dù model bị lừa, bước 3 vẫn chặn được — vì nó là code.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import ToolCall, ToolResult
from app.harness.tools.registry import RegisteredTool, Risk, ToolRegistry

if TYPE_CHECKING:
    from app.harness.governance.audit import AuditLog
    from app.harness.governance.policy_engine import PolicyProvider
    from app.harness.orchestration.approvals import ApprovalStore

AUTO_RUN_RISKS = frozenset({Risk.READ, Risk.WRITE})


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        auto_run: frozenset[Risk] = AUTO_RUN_RISKS,
        max_output_chars: int = 4_000,
        policy: PolicyProvider | None = None,
        approvals: ApprovalStore | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self.registry = registry
        self.auto_run = auto_run
        self.max_output_chars = max_output_chars
        self.policy = policy
        self.approvals = approvals
        self.audit = audit
        self.agent_name = ""  # BaseAgent gán — để policy/audit biết tool thuộc agent nào
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool")

    def execute(self, call: ToolCall, *, step: int = 0, tracer: Tracer | None = None) -> ToolResult:
        start = time.perf_counter()
        tool = self.registry.get(call.name)
        risk = tool.risk if tool else None
        output, is_error, status = self._run(call, tool, tracer.run_id if tracer else "")
        if not is_error:
            output = self._shrink(output)
        latency_ms = round((time.perf_counter() - start) * 1000)
        if tracer:
            tracer.event("tool_call", step=step, call_id=call.id, name=call.name, risk=risk, args=call.args,
                         status=status, output=output, is_error=is_error, latency_ms=latency_ms)
        if self.audit and tool and tool.risk != Risk.READ and status in ("ok", "error", "denied"):
            self.audit.record(f"agent:{self.agent_name}", f"tool:{tool.name}", status,
                              {"args": to_jsonable_python(call.args, fallback=str), "risk": tool.risk})
        return ToolResult(call.id, call.name, output, is_error)

    def _run(self, call: ToolCall, tool: RegisteredTool | None, run_id: str) -> tuple[Any, bool, str]:
        """Trả về (output, is_error, status). status dùng cho trace/metrics/audit."""
        if tool is None:
            available = ", ".join(self.registry.names())
            return f"Không có tool tên '{call.name}'. Các tool hiện có: {available}.", True, "unknown_tool"

        # Kiểm tra tham số TRƯỚC policy: yêu cầu duyệt chỉ được tạo với tham số hợp lệ.
        try:
            args = tool.args_model.model_validate(call.args)
        except ValidationError as e:
            return _explain_validation_error(e), True, "invalid_args"
        kwargs = {name: getattr(args, name) for name in type(args).model_fields}

        verdict = self._decide(tool)
        if verdict == "deny":
            return self._deny_reason(tool), True, "denied"
        if verdict == "require_approval":
            if self.approvals is None:
                # Nói rõ cho model biết để nó báo lại người dùng, thay vì thử lách bằng tool khác.
                message = (f"Tool '{tool.name}' có mức rủi ro '{tool.risk}' nên cần người dùng duyệt trước "
                           "khi chạy. Chưa có gì được thực hiện. Hãy báo cho người dùng biết.")
                return message, True, "needs_approval"
            summary = _safe_describe(tool, kwargs)
            pa = self.approvals.create(tool.name, args.model_dump(mode="json"), agent=self.agent_name,
                                       risk=tool.risk, summary=summary, run_id=run_id)
            return {"approval_id": pa.id, "status": "pending_approval",
                    "message": (f"Đã tạo yêu cầu duyệt #{pa.id}. CHƯA thực hiện — người dùng cần bấm Duyệt "
                                "trên Telegram hoặc web. Hãy báo rõ điều này cho người dùng."),
                    "what_will_happen": summary}, False, "pending_approval"

        future = self._pool.submit(tool.fn, **kwargs)
        try:
            return future.result(timeout=tool.timeout_s), False, "ok"
        except FutureTimeout:
            # Lưu ý: Python không "giết" được thread — hàm vẫn chạy nốt ở nền, ta chỉ thôi chờ.
            # Vì vậy tool ghi dữ liệu phải tự có timeout ở tầng I/O (DB, HTTP) — không dựa vào đây.
            return f"Tool '{tool.name}' quá thời gian {tool.timeout_s}s.", True, "timeout"
        except Exception as e:  # cố ý bắt mọi lỗi: trả cho model đọc để tự sửa
            return f"{type(e).__name__}: {e}", True, "error"

    def _decide(self, tool: RegisteredTool) -> str:
        if self.policy is None:
            return "allow" if tool.risk in self.auto_run else "require_approval"
        return self.policy.get().decide(tool.name, tool.risk, self.agent_name).decision

    def _deny_reason(self, tool: RegisteredTool) -> str:
        reason = self.policy.get().decide(tool.name, tool.risk, self.agent_name).reason if self.policy else ""
        return f"Không được phép dùng tool '{tool.name}': {reason} Hãy báo cho người dùng biết."

    def _shrink(self, output: Any) -> Any:
        """Đưa output về dạng JSON được; quá dài thì cắt và NÓI RÕ là đã cắt (model không bị hiểu lầm)."""
        data = to_jsonable_python(output, fallback=str)
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        if len(text) <= self.max_output_chars:
            return data
        return (text[: self.max_output_chars]
                + f"… [đã cắt, tổng {len(text)} ký tự — hãy yêu cầu dữ liệu hẹp hơn]")


def _safe_describe(tool: RegisteredTool, kwargs: dict[str, Any]) -> str:
    """Mô tả cho người duyệt. Lỗi khi mô tả không được chặn việc tạo yêu cầu — dùng mô tả thô."""
    raw = f"{tool.name}({json.dumps(to_jsonable_python(kwargs, fallback=str), ensure_ascii=False)})"
    if tool.describe is None:
        return raw
    try:
        return tool.describe(**kwargs)
    except Exception:
        return raw


def _explain_validation_error(e: ValidationError) -> str:
    problems = "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or '(chung)'}: {err['msg']}" for err in e.errors()
    )
    return f"Tham số không hợp lệ — {problems}. Hãy gọi lại với tham số đúng schema."
