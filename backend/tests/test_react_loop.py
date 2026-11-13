"""Test vòng ReAct bằng LLM GIẢ: kịch bản response viết sẵn → không gọi mạng, không tốn tiền,
kết quả lặp lại được. Kiểm tra LOGIC của vòng lặp, không kiểm tra độ thông minh của model (đó là eval)."""

import json
from typing import Any

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import LLMResponse, ToolCall, ToolResult, ToolSpec, Usage
from app.harness.orchestration.react_loop import Tool, run_react


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


ADD = Tool(ToolSpec("add", "Cộng hai số", {"type": "object"}), lambda a, b: a + b)


def boom() -> None:
    raise ValueError("hỏng rồi")


BOOM = Tool(ToolSpec("boom", "Luôn lỗi", {"type": "object"}), boom)


def test_answers_directly_without_tools():
    llm = FakeLLM(["Xin chào!"])
    result = run_react(llm, "sys", "chào", [ADD])
    assert (result.status, result.answer, result.steps) == ("ok", "Xin chào!", 1)


def test_runs_tool_and_feeds_observation_back():
    llm = FakeLLM([[ToolCall("c1", "add", {"a": 2, "b": 3})], "Kết quả là 5"])
    result = run_react(llm, "sys", "2+3?", [ADD])

    assert result.status == "ok" and result.steps == 2
    # Lượt 2 phải thấy: câu hỏi → lượt của model → kết quả tool (đúng thứ tự, đúng id).
    user, model_turn, tool_msg = llm.seen_histories[1]
    assert user["text"] == "2+3?" and model_turn["role"] == "model"
    assert tool_msg["results"] == [ToolResult("c1", "add", 5)]
    assert result.usage == Usage(20, 10, 4)  # cộng dồn qua các bước


def test_parallel_calls_go_back_in_one_message_in_order():
    calls = [ToolCall("c1", "add", {"a": 1, "b": 1}), ToolCall("c2", "add", {"a": 2, "b": 2})]
    llm = FakeLLM([calls, "xong"])
    run_react(llm, "sys", "?", [ADD])
    assert [r.output for r in llm.seen_histories[1][2]["results"]] == [2, 4]


def test_tool_exception_becomes_error_observation():
    llm = FakeLLM([[ToolCall("c1", "boom", {})], "Tool lỗi, tôi xin lỗi"])
    result = run_react(llm, "sys", "?", [BOOM])
    observation = llm.seen_histories[1][2]["results"][0]
    assert observation.is_error and "ValueError: hỏng rồi" in observation.output
    assert result.status == "ok"  # run không sập


def test_unknown_tool_and_bad_args_are_errors_too():
    llm = FakeLLM([[ToolCall("c1", "nope", {}), ToolCall("c2", "add", {"x": 1})], "ok"])
    run_react(llm, "sys", "?", [ADD])
    r1, r2 = llm.seen_histories[1][2]["results"]
    assert r1.is_error and "nope" in r1.output
    assert r2.is_error and "TypeError" in r2.output


def test_stops_at_max_steps():
    llm = FakeLLM([[ToolCall(f"c{i}", "add", {"a": 1, "b": 1})] for i in range(10)])
    result = run_react(llm, "sys", "?", [ADD], max_steps=3)
    assert result.status == "max_steps" and result.steps == 3
    assert len(llm.seen_histories) == 3  # không gọi LLM quá giới hạn


def test_tracer_writes_every_event_as_jsonl(tmp_path):
    tracer = Tracer(directory=tmp_path)
    llm = FakeLLM([[ToolCall("c1", "add", {"a": 2, "b": 3})], "5"])
    run_react(llm, "sys", "2+3?", [ADD], tracer=tracer)

    events = [json.loads(line) for line in tracer.path.read_text(encoding="utf-8").splitlines()]
    assert [e["type"] for e in events] == [
        "run_start", "llm_request", "llm_response", "tool_call", "llm_request", "llm_response", "run_end",
    ]
    assert events[0]["tools"][0]["name"] == "add"
    assert events[3]["args"] == {"a": 2, "b": 3} and events[3]["output"] == 5
    assert {e["run_id"] for e in events} == {tracer.run_id}
