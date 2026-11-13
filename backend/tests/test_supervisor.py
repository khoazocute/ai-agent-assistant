"""Supervisor (multi-agent) với LLM giả: giao việc, run con liên kết, cộng dồn token."""

from conftest import NOW
from fakes import FakeLLM

from app.agents.supervisor.agent import SupervisorAgent
from app.harness.agentops.cost import Pricing
from app.harness.agentops.store import DbTraceSink, child_runs, run_events
from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import ToolCall, Usage
from app.integrations.email_provider import FakeEmailProvider
from evals.run import EvalCase, run_case


def test_supervisor_delegates_and_links_child_runs(session_factory):
    # FakeLLM dùng chung: lượt được tiêu thụ theo đúng thứ tự gọi (supervisor → finance → supervisor).
    llm = FakeLLM([
        [ToolCall("s1", "ask_finance_agent", {"request": "trưa nay ăn phở 45k"})],     # supervisor
        [ToolCall("f1", "add_transaction", {"amount_vnd": 45000, "category": "an_uong"})],  # finance
        "Đã ghi 45.000đ ăn uống.",                                                    # finance trả lời
        "Đã ghi khoản ăn phở 45.000đ.",                                               # supervisor tổng hợp
    ])
    tracer = Tracer(sinks=[DbTraceSink(session_factory, Pricing())])
    agent = SupervisorAgent(llm, session_factory, FakeEmailProvider(), now=lambda: NOW)
    result = agent.run("trưa nay ăn phở 45k", tracer)

    assert result.status == "ok" and result.answer.startswith("Đã ghi")
    assert [c.name for c in result.tool_calls] == ["ask_finance_agent", "add_transaction"]
    assert result.usage == Usage(40, 20, 8)  # 2 lượt supervisor + 2 lượt finance

    (child,) = child_runs(session_factory, tracer.run_id)
    assert (child.agent, child.status, child.parent_run_id) == ("finance", "ok", tracer.run_id)
    _, events = run_events(session_factory, tracer.run_id)
    observation = next(e for e in events if e.type == "tool_call")
    assert observation.data["output"]["agent"] == "finance"
    assert observation.data["output"]["tools_used"] == ["add_transaction"]


def test_sub_agent_only_sees_delegated_request_and_has_no_ask_tools(session_factory):
    llm = FakeLLM([[ToolCall("s", "ask_schedule_agent", {"request": "chiều mai 3h họp nhóm"})], "ok", "ok"])
    SupervisorAgent(llm, session_factory, FakeEmailProvider(), now=lambda: NOW).run(
        "trưa ăn phở 45k, chiều mai 3h họp nhóm")
    sub_first_message = llm.seen_histories[1][0]["text"]
    assert sub_first_message.endswith("chiều mai 3h họp nhóm") and "phở" not in sub_first_message
    assert not any(t.name.startswith("ask_") for t in llm.seen_tools[1])  # độ sâu ủy quyền = 1


def test_cross_domain_eval_case_with_supervisor():
    case = EvalCase.model_validate({"id": "m", "input": "trưa ăn phở 45k, chiều mai 3h họp nhóm", "expect": {
        "transactions": [{"amount_vnd": 45000, "category": "an_uong", "occurred_on": "today"}],
        "events": [{"title_contains": "họp", "start": "2026-11-14T15:00"}],
        "must_call": ["create_event"]}})
    llm = FakeLLM([
        [ToolCall("a", "ask_finance_agent", {"request": "trưa ăn phở 45k"}),
         ToolCall("b", "ask_schedule_agent", {"request": "chiều mai 3h họp nhóm"})],
        [ToolCall("f", "add_transaction", {"amount_vnd": 45000, "category": "an_uong"})], "Đã ghi.",
        [ToolCall("e", "create_event", {"title": "Họp nhóm", "start_at": "2026-11-14T15:00", "duration_min": 60})],
        "Đã tạo.",
        "Xong cả hai việc.",
    ])
    r = run_case(case, llm, agent="supervisor")
    assert r.passed, [c.name for c in r.failed_checks]  # must_call nhìn thấy tool của sub-agent
