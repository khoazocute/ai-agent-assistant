"""Trace vào DB, chi phí, số liệu vận hành."""

from fakes import FakeLLM

from app.harness.agentops.cost import ModelPrice, Pricing
from app.harness.agentops.metrics import agent_stats, percentile
from app.harness.agentops.store import DbTraceSink, child_runs, recent_runs, run_events
from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import ToolCall
from app.harness.orchestration.react_loop import run_react
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool


@agent_tool(risk=Risk.READ)
def add(a: int, b: int) -> int:
    """Cộng hai số."""
    return a + b


EXECUTOR = ToolExecutor(ToolRegistry([add]))
PRICING = Pricing({"fake": ModelPrice(input_per_1m_usd=1.0, output_per_1m_usd=4.0)}, usd_to_vnd=25_000)


def traced_run(factory, script, parent: Tracer | None = None, agent="calc"):
    sink = DbTraceSink(factory, PRICING, channel="test")
    tracer = parent.child() if parent else Tracer(sinks=[sink])
    run_react(FakeLLM(script), "sys", "2+3?", EXECUTOR, tracer=tracer, meta={"agent": agent, "prompt_version": "v1"})
    return tracer


def test_run_is_stored_with_totals_and_every_event(session_factory):
    tracer = traced_run(session_factory, [[ToolCall("c1", "add", {"a": 2, "b": 3})], "5"])
    run, events = run_events(session_factory, tracer.run_id)

    assert (run.agent, run.status, run.output, run.steps, run.tool_calls) == ("calc", "ok", "5", 2, 1)
    assert (run.channel, run.prompt_version, run.model) == ("test", "v1", "fake")
    assert (run.input_tokens, run.output_tokens, run.thinking_tokens) == (20, 10, 4)
    assert run.cost_usd == (20 * 1.0 + (10 + 4) * 4.0) / 1_000_000  # thinking tính như token ra
    assert run.latency_ms is not None and run.ended_at is not None
    assert [e.type for e in events] == [
        "run_start", "llm_request", "llm_response", "tool_call", "llm_request", "llm_response", "run_end"]
    assert events[0].data["system"] == "sys"  # prompt được lưu nguyên văn
    assert events[3].data["args"] == {"a": 2, "b": 3}


def test_run_id_prefix_lookup(session_factory):
    tracer = traced_run(session_factory, ["xin chào"])
    assert run_events(session_factory, tracer.run_id[:15])[0].run_id == tracer.run_id


def test_child_run_links_to_parent(session_factory):
    parent = Tracer(sinks=[DbTraceSink(session_factory, PRICING)])
    parent.event("run_start", agent="supervisor", input="?", tools=[])
    child = traced_run(session_factory, ["con"], parent=parent, agent="finance")
    assert [c.run_id for c in child_runs(session_factory, parent.run_id)] == [child.run_id]
    assert [r.run_id for r in recent_runs(session_factory)] == [parent.run_id]  # chỉ run cấp cao nhất


def test_unknown_model_price_gives_none_not_a_guess():
    assert Pricing().cost_usd("gemini-x", 1000, 1000) is None
    assert Pricing(usd_to_vnd=25_000).to_vnd(None) is None
    assert PRICING.to_vnd(0.001) == 25


def test_percentile_nearest_rank():
    data = list(range(1, 101))  # 1..100
    assert (percentile(data, 50), percentile(data, 95)) == (50, 95)
    assert percentile([7], 95) == 7 and percentile([], 50) is None


def test_agent_stats(session_factory):
    traced_run(session_factory, ["a"])
    traced_run(session_factory, [[ToolCall("c", "add", {"a": 1, "b": 1})], "b"])
    (s,) = agent_stats(session_factory)
    assert (s.agent, s.runs, s.ok, s.success_rate, s.avg_steps) == ("calc", 2, 2, 1.0, 1.5)
    assert s.total_cost_usd is not None and s.p95_ms is not None
