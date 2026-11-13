"""Finance tools + agent với LLM giả: kiểm tra đường đi model → tool → service → DB (không kiểm tra
model có hiểu tiếng Việt không — đó là việc của eval ở bước 5)."""

from conftest import NOW, TODAY
from fakes import FakeLLM

from app.agents.finance.agent import FinanceAgent
from app.agents.finance.tools import build_finance_tools
from app.db.session import session_scope
from app.harness.orchestration.llm_client import ToolCall
from app.harness.tools.executor import ToolExecutor
from app.services.finance_service import FinanceService


def executor(session_factory):
    return ToolExecutor(build_finance_tools(session_factory, today=lambda: TODAY))


def call(ex, name, **args):
    return ex.execute(ToolCall("id", name, args))


def all_transactions(session_factory):
    with session_scope(session_factory) as s:
        return FinanceService(s).list_transactions(limit=50)


def test_category_schema_is_an_enum_model_must_pick_from():
    specs = {s.name: s for s in build_finance_tools(None).specs()}  # schema không cần DB
    category = specs["add_transaction"].parameters["properties"]["category"]
    assert "phu_cap_gia_dinh" in category["enum"]
    assert specs["add_transaction"].parameters["required"] == ["amount_vnd", "category"]


def test_add_transaction_tool_writes_to_db(session_factory):
    r = call(executor(session_factory), "add_transaction", amount_vnd=45000, category="an_uong", note="phở")
    assert not r.is_error and r.output["amount_vnd"] == 45000 and r.output["occurred_on"] == "2026-11-13"
    assert [t.note for t in all_transactions(session_factory)] == ["phở"]


def test_invalid_tool_args_never_reach_db(session_factory):
    ex = executor(session_factory)
    assert call(ex, "add_transaction", amount_vnd=-45000, category="an_uong").is_error  # Field(gt=0)
    assert call(ex, "add_transaction", amount_vnd=45000, category="food").is_error  # ngoài enum
    assert call(ex, "add_transaction", amount_vnd="45k", category="an_uong").is_error  # không phải số
    assert all_transactions(session_factory) == []


def test_summary_tool_resolves_period_in_code(session_factory):
    ex = executor(session_factory)
    call(ex, "add_transaction", amount_vnd=200_000, category="mua_sam", occurred_on="2026-11-02")
    call(ex, "add_transaction", amount_vnd=50_000, category="thu_nhap")
    r = call(ex, "get_summary", period="this_month")
    assert (r.output["start"], r.output["end"], r.output["net_spending_vnd"]) == ("2026-11-01", "2026-11-30", 150_000)
    assert call(ex, "get_summary").is_error  # không có period lẫn start/end → lỗi rõ ràng


def test_delete_is_blocked_and_data_stays(session_factory):
    ex = executor(session_factory)
    tid = call(ex, "add_transaction", amount_vnd=10_000, category="khac").output["id"]
    r = call(ex, "delete_transaction", transaction_id=tid)
    assert r.is_error and "duyệt" in r.output
    assert len(all_transactions(session_factory)) == 1


def test_agent_logs_two_items_from_one_message(session_factory):
    llm = FakeLLM([
        [ToolCall("c1", "add_transaction", {"amount_vnd": 45000, "category": "an_uong", "note": "phở"}),
         ToolCall("c2", "add_transaction", {"amount_vnd": 60000, "category": "di_chuyen", "note": "xăng"})],
        "Đã ghi 2 khoản.",
    ])
    agent = FinanceAgent(llm, session_factory, now=lambda: NOW)
    result = agent.run("trưa ăn phở 45k, đổ xăng 60k")

    assert result.status == "ok" and result.steps == 2
    assert sorted(t.amount_vnd for t in all_transactions(session_factory)) == [45000, 60000]
    # Model nhận được thời điểm hiện tại trong USER message (system prompt giữ nguyên).
    assert llm.seen_histories[0][0]["text"].startswith("[Thời điểm hiện tại: Thứ Sáu 13/11/2026 12:30")
    assert {s.name for s in llm.seen_tools[0]} == {
        "add_transaction", "get_summary", "list_transactions", "delete_transaction"}


def test_agent_prompt_has_stable_version():
    from app.agents.finance.agent import PROMPT_PATH
    from app.harness.context.prompts import load_prompt

    p1, p2 = load_prompt(PROMPT_PATH), load_prompt(PROMPT_PATH)
    assert p1.version == p2.version and len(p1.version) == 8
    assert p1.meta["agent"] == "finance" and not p1.text.startswith("---")
