"""Test vòng ReAct bằng LLM GIẢ: kịch bản response viết sẵn → không gọi mạng, không tốn tiền,
kết quả lặp lại được. Kiểm tra LOGIC của vòng lặp, không kiểm tra độ thông minh của model (đó là eval)."""

import json
from typing import Any

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import LLMResponse, ToolCall, ToolResult, ToolSpec, Usage
from app.harness.orchestration.react_loop import run_react
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool


class FakeLLM:
    model = "fake"

    def __init__(self, script: list[list[ToolCall] | str]) -> None:
        # Mỗi phần tử là một lượt: list ToolCall (model muốn gọi tool) hoặc str (câu trả lời cuối).
        self.script = list(script)
        self.seen_histories: list[list[Any]] = []

    def user_message(self, text: str) -> Any:
        return {"role": "user", "text": text}

    def tool_results_message(self, results: list[ToolResult]) -> Any:
        return {"role": "tool", "results": results}

    def generate(self, system: str, history: list[Any], tools: list[ToolSpec]) -> LLMResponse:
        self.seen_histories.append(list(history))
        turn = self.script.pop(0)
        calls = [] if isinstance(turn, str) else turn
        text = turn if isinstance(turn, str) else ""
        return LLMResponse(text, ["thinking..."], calls, Usage(10, 5, 2), "STOP", 1,
                           message={"role": "model", "calls": calls, "text": text})


@agent_tool(risk=Risk.READ)
def add(a: int, b: int) -> int:
    """Cộng hai số."""
    return a + b


@agent_tool(risk=Risk.READ)
def boom() -> None:
    """Luôn lỗi."""
    raise ValueError("hỏng rồi")


EXECUTOR = ToolExecutor(ToolRegistry([add, boom]))


def observations(llm: FakeLLM, turn: int = 1) -> list[ToolResult]:
    """Kết quả tool mà model nhìn thấy ở lượt `turn` (message cuối của history)."""
    return llm.seen_histories[turn][-1]["results"]


def test_answers_directly_without_tools():
    llm = FakeLLM(["Xin chào!"])
    result = run_react(llm, "sys", "chào", EXECUTOR)
    assert (result.status, result.answer, result.steps) == ("ok", "Xin chào!", 1)


def test_runs_tool_and_feeds_observation_back():
    llm = FakeLLM([[ToolCall("c1", "add", {"a": 2, "b": 3})], "Kết quả là 5"])
    result = run_react(llm, "sys", "2+3?", EXECUTOR)

    assert result.status == "ok" and result.steps == 2
    # Lượt 2 phải thấy: câu hỏi → lượt của model → kết quả tool (đúng thứ tự, đúng id).
    user, model_turn, _ = llm.seen_histories[1]
    assert user["text"] == "2+3?" and model_turn["role"] == "model"
    assert observations(llm) == [ToolResult("c1", "add", 5)]
    assert result.usage == Usage(20, 10, 4)  # cộng dồn qua các bước


def test_parallel_calls_go_back_in_one_message_in_order():
    calls = [ToolCall("c1", "add", {"a": 1, "b": 1}), ToolCall("c2", "add", {"a": 2, "b": 2})]
    llm = FakeLLM([calls, "xong"])
    run_react(llm, "sys", "?", EXECUTOR)
    assert [r.output for r in observations(llm)] == [2, 4]


def test_tool_exception_becomes_error_observation():
    llm = FakeLLM([[ToolCall("c1", "boom", {})], "Tool lỗi, tôi xin lỗi"])
    result = run_react(llm, "sys", "?", EXECUTOR)
    (obs,) = observations(llm)
    assert obs.is_error and "ValueError: hỏng rồi" in obs.output
    assert result.status == "ok"  # run không sập


def test_stops_at_max_steps():
    llm = FakeLLM([[ToolCall(f"c{i}", "add", {"a": 1, "b": 1})] for i in range(10)])
    result = run_react(llm, "sys", "?", EXECUTOR, max_steps=3)
    assert result.status == "max_steps" and result.steps == 3
    assert len(llm.seen_histories) == 3  # không gọi LLM quá giới hạn


def test_tracer_writes_every_event_as_jsonl(tmp_path):
    tracer = Tracer(directory=tmp_path)
    llm = FakeLLM([[ToolCall("c1", "add", {"a": 2, "b": 3})], "5"])
    run_react(llm, "sys", "2+3?", EXECUTOR, tracer=tracer)

    events = [json.loads(line) for line in tracer.path.read_text(encoding="utf-8").splitlines()]
    assert [e["type"] for e in events] == [
        "run_start", "llm_request", "llm_response", "tool_call", "llm_request", "llm_response", "run_end",
    ]
    assert events[0]["tools"][0]["name"] == "add"
    tool_event = events[3]
    assert tool_event["args"] == {"a": 2, "b": 3} and tool_event["output"] == 5
    assert (tool_event["risk"], tool_event["status"]) == ("read", "ok")
    assert {e["run_id"] for e in events} == {tracer.run_id}
