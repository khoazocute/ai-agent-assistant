"""Test vòng ReAct bằng LLM GIẢ: kịch bản response viết sẵn → không gọi mạng, không tốn tiền,
kết quả lặp lại được. Kiểm tra LOGIC của vòng lặp, không kiểm tra độ thông minh của model (đó là eval)."""

import json

from fakes import FakeLLM

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import ToolCall, ToolResult, Usage
from app.harness.orchestration.react_loop import run_react
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool


@agent_tool(risk=Risk.READ)
def add(a: int, b: int) -> int:
    """Cộng hai số."""
    return a + b


@agent_tool(risk=Risk.READ)
def boom() -> None:
    """Luôn lỗi."""
    raise ValueError("hỏng rồi")


EXECUTOR = ToolExecutor(ToolRegistry([add, boom]))


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
    assert llm.observations() == [ToolResult("c1", "add", 5)]
    assert result.usage == Usage(20, 10, 4)  # cộng dồn qua các bước


def test_parallel_calls_go_back_in_one_message_in_order():
    calls = [ToolCall("c1", "add", {"a": 1, "b": 1}), ToolCall("c2", "add", {"a": 2, "b": 2})]
    llm = FakeLLM([calls, "xong"])
    run_react(llm, "sys", "?", EXECUTOR)
    assert [r.output for r in llm.observations()] == [2, 4]


def test_tool_exception_becomes_error_observation():
    llm = FakeLLM([[ToolCall("c1", "boom", {})], "Tool lỗi, tôi xin lỗi"])
    result = run_react(llm, "sys", "?", EXECUTOR)
    (obs,) = llm.observations()
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


def test_llm_failure_still_closes_the_run_in_trace(tmp_path):
    class BrokenLLM(FakeLLM):
        def generate(self, *args):
            raise ConnectionError("503 quá tải")

    tracer = Tracer(directory=tmp_path)
    try:
        run_react(BrokenLLM([]), "sys", "?", EXECUTOR, tracer=tracer)
    except ConnectionError:
        pass
    last = json.loads(tracer.path.read_text(encoding="utf-8").splitlines()[-1])
    assert (last["type"], last["status"]) == ("run_end", "error") and "503" in last["error"]
