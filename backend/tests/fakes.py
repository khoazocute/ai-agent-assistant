"""LLM giả cho test: phát lại kịch bản viết sẵn → không gọi mạng, không tốn tiền, lặp lại được."""

from typing import Any

from app.harness.orchestration.llm_client import LLMResponse, ToolCall, ToolResult, ToolSpec, Usage


class FakeLLM:
    model = "fake"

    def __init__(self, script: list[list[ToolCall] | str]) -> None:
        # Mỗi phần tử là một lượt: list ToolCall (model muốn gọi tool) hoặc str (câu trả lời cuối).
        self.script = list(script)
        self.seen_histories: list[list[Any]] = []
        self.seen_tools: list[list[ToolSpec]] = []

    def user_message(self, text: str) -> Any:
        return {"role": "user", "text": text}

    def assistant_message(self, text: str) -> Any:
        return {"role": "model", "text": text}

    def tool_results_message(self, results: list[ToolResult]) -> Any:
        return {"role": "tool", "results": results}

    def generate(self, system: str, history: list[Any], tools: list[ToolSpec]) -> LLMResponse:
        self.seen_histories.append(list(history))
        self.seen_tools.append(tools)
        turn = self.script.pop(0)
        calls = [] if isinstance(turn, str) else turn
        text = turn if isinstance(turn, str) else ""
        return LLMResponse(text, ["thinking..."], calls, Usage(10, 5, 2), "STOP", 1,
                           message={"role": "model", "calls": calls, "text": text})

    def observations(self, turn: int = 1) -> list[ToolResult]:
        """Kết quả tool mà model nhìn thấy ở lượt `turn` (message cuối của history)."""
        return self.seen_histories[turn][-1]["results"]
