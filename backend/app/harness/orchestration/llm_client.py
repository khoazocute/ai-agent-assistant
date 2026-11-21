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

    def assistant_message(self, text: str) -> Any: ...

    def tool_results_message(self, results: list[ToolResult]) -> Any: ...

    def generate(self, system: str, history: list[Any], tools: list[ToolSpec]) -> LLMResponse: ...


class StructuredLLM(Protocol):
    """LLM trích xuất dữ liệu có cấu trúc (JSON theo schema), có thể kèm ảnh — dùng cho workflow (bước 17)."""

    model: str

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any], image: bytes | None = None,
                      mime_type: str | None = None) -> tuple[dict[str, Any], LLMResponse]: ...


# ---------- Adapter cho Google Gemini (ADR-0002) ----------


class GeminiClient:
    """Adapter Gemini có MODEL DỰ PHÒNG: model đang dùng hết quota (429) hoặc đang quá tải (500/503/504,
    gặp thật 18/11 — "high demand") → chuyển sang model kế tiếp.

    Mỗi model Gemini có quota riêng (gói miễn phí ~20 request/ngày/model) → 3 model ≈ 60 request/ngày.
    Model hết quota bị "nghỉ" `cooldown_s` giây (mặc định 1 giờ) rồi mới thử lại (quota có thể đã hồi).
    Model đang quá tải tạm thời chỉ "nghỉ" `overload_cooldown_s` giây (mặc định 1 phút) — khác lý do
    nên khác thời gian nghỉ: quá tải thường hết rất nhanh, không nên né model chính cả giờ vì nó.
    429 KHÔNG nằm trong danh sách SDK tự retry: hết quota ngày thì thử lại cùng model chỉ phí ~40 giây.
    500/503/504 ĐÃ được SDK tự thử lại vài lần trên cùng model trước khi rơi tới đây — đổi model lúc
    này là thử một máy chủ/model khác, không phải lặp lại việc SDK vừa làm.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_ms: int = 45_000,
        attempts: int = 5,
        fallback_models: list[str] | None = None,
        cooldown_s: float = 3600,
        overload_cooldown_s: float = 60,
    ) -> None:
        # Import ở đây để code/test không dùng Gemini (vd. FakeLLM) không cần cài SDK.
        from google import genai
        from google.genai import errors, types

        self._types = types
        self._errors = errors
        primary = model or os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
        self.models = list(dict.fromkeys([primary, *(fallback_models or [])]))  # bỏ trùng, giữ thứ tự
        self.model = primary  # model của lượt gọi gần nhất — ghi vào trace
        self.cooldown_s = cooldown_s
        self.overload_cooldown_s = overload_cooldown_s
        self._exhausted_until: dict[str, float] = {}
        self._last_error: dict[str, Exception] = {}  # vì sao model đang "nghỉ" — để báo đúng lý do
        self._client = genai.Client(
            api_key=api_key or os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(
                timeout=timeout_ms,
                # Chỉ thử lại lỗi TẠM THỜI của máy chủ. 400/404 do yêu cầu sai — thử lại vô ích;
                # 429 (hết quota) được xử lý bằng cách đổi model (_with_fallback), không thử lại cùng model.
                retry_options=types.HttpRetryOptions(
                    attempts=attempts, initial_delay=2.0, max_delay=20.0,
                    http_status_codes=[500, 503, 504],
                ),
            ),
        )

    def _with_fallback(self, call: Any) -> Any:
        """Gọi `call(model)` lần lượt theo danh sách model; 429 (hết quota) và 500/503/504 (quá tải) đều
        chuyển sang model kế tiếp, mỗi lý do nghỉ một thời gian khác nhau; lỗi khác ném ra ngay."""
        now = time.monotonic()
        candidates = [m for m in self.models if self._exhausted_until.get(m, 0) <= now]
        last_error: Exception | None = None
        for model in candidates:
            try:
                result = call(model)
            except self._errors.APIError as e:
                if e.code == 429:
                    self._exhausted_until[model] = time.monotonic() + self.cooldown_s
                elif e.code in (500, 503, 504):
                    self._exhausted_until[model] = time.monotonic() + self.overload_cooldown_s
                else:
                    raise
                self._last_error[model] = e
                last_error = e
                continue
            self.model = model
            return result
        if last_error is not None:
            raise last_error
        # candidates rỗng NGAY TỪ ĐẦU (mọi model còn đang "nghỉ" từ lượt gọi trước, vòng for không chạy
        # lần nào) → ném lại đúng lỗi đã khiến model đó bị cho nghỉ, đừng fabricate "hết quota": có thể
        # tất cả đang quá tải (503/504) chứ không phải hết quota ngày, hai lý do cần báo khác nhau.
        for model in self.models:
            if model in self._last_error:
                raise self._last_error[model]
        raise self._errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                                       "message": f"Tất cả model đã hết quota: {self.models}"}})

    def user_message(self, text: str) -> Any:
        t = self._types
        return t.Content(role="user", parts=[t.Part(text=text)])

    def assistant_message(self, text: str) -> Any:
        """Câu trả lời CŨ của model (memory hội thoại) — chỉ phần chữ, không kèm tool call cũ."""
        t = self._types
        return t.Content(role="model", parts=[t.Part(text=text)])

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
        resp = self._with_fallback(
            lambda model: self._client.models.generate_content(model=model, contents=history, config=config))
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

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any], image: bytes | None = None,
                      mime_type: str | None = None) -> tuple[dict[str, Any], LLMResponse]:
        """Một lượt gọi KHÔNG tool, đầu ra bị ép đúng JSON schema (structured output) — model không thể
        "trả lời tự do" hay làm theo chữ trong ảnh, chỉ có thể điền các trường đã định."""
        import json

        t = self._types
        parts = [t.Part(text=prompt)]
        if image is not None:
            parts.insert(0, t.Part.from_bytes(data=image, mime_type=mime_type or "image/jpeg"))
        config = t.GenerateContentConfig(
            system_instruction=system, response_mime_type="application/json", response_json_schema=schema,
            thinking_config=t.ThinkingConfig(include_thoughts=True),
        )
        start = time.perf_counter()
        contents = [t.Content(role="user", parts=parts)]
        resp = self._with_fallback(
            lambda model: self._client.models.generate_content(model=model, contents=contents, config=config))
        latency_ms = round((time.perf_counter() - start) * 1000)
        um = resp.usage_metadata
        usage = Usage((um.prompt_token_count or 0) if um else 0, (um.candidates_token_count or 0) if um else 0,
                      (um.thoughts_token_count or 0) if um else 0)
        content = resp.candidates[0].content if resp.candidates else None
        texts = [p.text for p in (content.parts if content else []) or [] if p.text and not p.thought]
        thoughts = [p.text.strip() for p in (content.parts if content else []) or [] if p.thought and p.text]
        raw = "".join(texts).strip()
        data = json.loads(raw) if raw else {}
        return data, LLMResponse(raw, thoughts, [], usage, "STOP", latency_ms, content)
