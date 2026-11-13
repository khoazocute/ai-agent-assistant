"""LLM client — chỗ DUY NHẤT trong dự án biết về SDK của nhà cung cấp LLM.

Vòng ReAct chỉ làm việc với các kiểu trung lập bên dưới (ToolSpec, ToolCall, ToolResult, LLMResponse).
Muốn thêm Claude/OpenAI: viết một class mới có cùng 3 phương thức như GeminiClient — không sửa react_loop.

Lịch sử hội thoại (`history`) là danh sách message ĐÚNG ĐỊNH DẠNG CỦA PROVIDER, vòng lặp coi nó là
hộp đen: chỉ tạo qua `user_message` / `tool_results_message` và nối `LLMResponse.message` vào.
Lý do: Gemini yêu cầu gửi lại nguyên vẹn nội dung model trả (kèm thought signature); nếu tự chuyển
qua lại định dạng trung lập thì dễ làm rơi mất những trường đó.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

# ---------- Kiểu dữ liệu trung lập provider ----------


@dataclass
class ToolSpec:
    """Thứ model NHÌN THẤY về một tool: tên, mô tả (khi nào dùng), JSON schema của tham số."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    """Model đề nghị gọi tool (Action). Code của mình quyết định có chạy hay không."""

    id: str | None
    name: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    """Kết quả chạy tool (Observation). Lỗi cũng là Observation: is_error=True để model tự sửa."""

    call_id: str | None
    name: str
    output: Any
    is_error: bool = False


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.thinking_tokens + other.thinking_tokens,
        )


@dataclass
class LLMResponse:
    text: str  # câu trả lời (không gồm thought)
    thoughts: list[str]  # tóm tắt suy luận (Thought)
    tool_calls: list[ToolCall]  # rỗng ⇔ model đã trả lời xong
    usage: Usage
    finish_reason: str
    latency_ms: int
    message: Any = field(repr=False)  # message gốc của provider — nối nguyên vẹn vào history


class LLMClient(Protocol):
    model: str

    def user_message(self, text: str) -> Any: ...

    def tool_results_message(self, results: list[ToolResult]) -> Any: ...

    def generate(self, system: str, history: list[Any], tools: list[ToolSpec]) -> LLMResponse: ...


# ---------- Adapter cho Google Gemini (ADR-0002) ----------


class GeminiClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_ms: int = 45_000,
        attempts: int = 5,
    ) -> None:
        # Import ở đây để code/test không dùng Gemini (vd. FakeLLM) không cần cài SDK.
        from google import genai
        from google.genai import types

        self._types = types
        self.model = model or os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
        self._client = genai.Client(
            api_key=api_key or os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(
                timeout=timeout_ms,
                # Chỉ thử lại lỗi TẠM THỜI. 400/404 là lỗi do yêu cầu sai — thử lại vô ích.
                retry_options=types.HttpRetryOptions(
                    attempts=attempts, initial_delay=2.0, max_delay=20.0,
                    http_status_codes=[429, 500, 503, 504],
                ),
            ),
        )

    def user_message(self, text: str) -> Any:
        t = self._types
        return t.Content(role="user", parts=[t.Part(text=text)])

    def tool_results_message(self, results: list[ToolResult]) -> Any:
        t = self._types
        parts = [
            t.Part(function_response=t.FunctionResponse(
                id=r.call_id,
                name=r.name,
                # Quy ước của Gemini: khoá "output" khi thành công, "error" khi lỗi.
                response={"error": r.output} if r.is_error else {"output": r.output},
            ))
            for r in results
        ]
        # Mọi kết quả của một lượt nằm trong MỘT message, theo đúng thứ tự lời gọi.
        return t.Content(role="user", parts=parts)

    def generate(self, system: str, history: list[Any], tools: list[ToolSpec]) -> LLMResponse:
        t = self._types
        declarations = [
            t.FunctionDeclaration(name=s.name, description=s.description, parameters_json_schema=s.parameters)
            for s in tools
        ]
        config = t.GenerateContentConfig(
            system_instruction=system or None,
            tools=[t.Tool(function_declarations=declarations)] if declarations else None,
            thinking_config=t.ThinkingConfig(include_thoughts=True),
            # Tắt chế độ SDK tự chạy hàm: vòng ReAct là của MÌNH (ADR-0003).
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )
        start = time.perf_counter()
        resp = self._client.models.generate_content(model=self.model, contents=history, config=config)
        latency_ms = round((time.perf_counter() - start) * 1000)

        um = resp.usage_metadata
        usage = Usage(
            input_tokens=(um.prompt_token_count or 0) if um else 0,
            output_tokens=(um.candidates_token_count or 0) if um else 0,
            thinking_tokens=(um.thoughts_token_count or 0) if um else 0,
        )

        if not resp.candidates or resp.candidates[0].content is None:
            # Bị chặn (an toàn) hoặc không sinh được gì — trả rỗng để vòng lặp kết thúc có kiểm soát.
            reason = resp.prompt_feedback.block_reason if resp.prompt_feedback else "NO_CANDIDATE"
            return LLMResponse("", [], [], usage, str(reason), latency_ms, t.Content(role="model", parts=[]))

        candidate = resp.candidates[0]
        thoughts, texts, calls = [], [], []
        for part in candidate.content.parts or []:
            if part.thought:
                thoughts.append((part.text or "").strip())
            elif part.function_call:
                fc = part.function_call
                calls.append(ToolCall(id=fc.id, name=fc.name, args=dict(fc.args or {})))
            elif part.text:
                texts.append(part.text)

        finish = candidate.finish_reason.name if candidate.finish_reason else "UNKNOWN"
        text = "".join(texts).strip()
        return LLMResponse(text, thoughts, calls, usage, finish, latency_ms, candidate.content)
