"""Governance: policy-as-code, yêu cầu duyệt (thực thi đúng thứ đã duyệt), audit, kill switch."""

import sys
from datetime import timedelta

import pytest
from conftest import NOW
from fakes import FakeLLM

from app import cli
from app.db.session import session_scope
from app.harness.governance.audit import AuditLog
from app.harness.governance.policy_engine import Decision, Policy, PolicyProvider
from app.harness.orchestration.approvals import ApprovalError, ApprovalStore
from app.harness.orchestration.llm_client import ToolCall
from app.integrations.email_provider import FakeEmailProvider, RawEmail
from app.runtime import Runtime
from app.services.finance_service import FinanceService

# ---------- Policy ----------


@pytest.mark.parametrize(("tool", "risk", "agent", "expected"), [
    ("list_transactions", "read", "finance", Decision.ALLOW),
    ("add_transaction", "write", "finance", Decision.ALLOW),
    ("delete_event", "destructive", "schedule", Decision.REQUIRE_APPROVAL),
    ("add_transaction", "write", "email", Decision.DENY),  # agent email bị tắt
    ("ask_email_agent", "read", "supervisor", Decision.DENY),  # tool ask_* của agent bị tắt
    ("get_summary", "read", "", Decision.DENY),  # tool bị tắt
])
def test_policy_decisions(tool, risk, agent, expected):
    policy = Policy.from_dict({"disabled_agents": ["email"], "disabled_tools": ["get_summary"]})
    assert policy.decide(tool, risk, agent).decision == expected


def test_external_can_never_be_allowed_even_if_yaml_says_so():
    policy = Policy.from_dict({"defaults": {"external": "allow"}, "tools": {"send_email": "allow"}})
    d = policy.decide("send_email", "external")
    assert d.decision == Decision.REQUIRE_APPROVAL and "luật cứng" in d.reason


def test_policy_file_hot_reload(tmp_path):
    path = tmp_path / "policies.yaml"
    path.write_text("disabled_tools: []\n", encoding="utf-8")
    provider = PolicyProvider(path)
    assert provider.get().decide("add_transaction", "write").decision == Decision.ALLOW
    path.write_text("disabled_tools: [add_transaction]\n", encoding="utf-8")
    import os
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))  # đảm bảo mtime đổi
    assert provider.get().decide("add_transaction", "write").decision == Decision.DENY


def test_repo_policies_yaml_is_valid():
    from app.config import CONFIG_DIR

    policy = Policy.load(CONFIG_DIR / "policies.yaml")
    assert policy.decide("send_email", "external").decision == Decision.REQUIRE_APPROVAL
    assert policy.decide("delete_transaction", "destructive").decision == Decision.REQUIRE_APPROVAL


# ---------- Duyệt: luồng đầy đủ qua Runtime ----------

@pytest.fixture
def rt():
    provider = FakeEmailProvider(inbox=[RawEmail("m1", "Minh <minh@congty.vn>", "Họp", "Chiều mai họp nhé",
                                                 NOW.replace(tzinfo=None) - timedelta(hours=1), thread_id="t1",
                                                 message_id_header="<m1@x>")])
    return Runtime.create("sqlite://", email_provider=provider, llm=FakeLLM([]))


def run_tool(rt: Runtime, agent: str, name: str, args: dict):
    executor = rt.agent(agent, now=lambda: NOW).executor
    return executor.execute(ToolCall("c", name, args))


def test_send_email_creates_pending_action_and_sends_only_after_approve(rt):
    draft = run_tool(rt, "email", "create_draft", {"to": ["minh@congty.vn"], "subject": "Re: Họp",
                                                   "body": "Em đồng ý. STK 0123456789"})
    r = run_tool(rt, "email", "send_email", {"draft_id": draft.output["id"]})
    assert not r.is_error and r.output["status"] == "pending_approval"
    assert rt.email_provider.sent == []  # CHƯA gửi

    (pa,) = rt.approvals.list("pending")
    assert "Tới: minh@congty.vn" in pa.summary and "Em đồng ý" in pa.summary and "nhạy cảm" in pa.summary

    done = rt.approve(pa.id, "user:test")
    assert done.status == "executed" and done.result["status"] == "sent"
    (sent,) = rt.email_provider.sent
    assert sent.body == "Em đồng ý. STK 0123456789"  # gửi ĐÚNG nội dung đã duyệt

    with pytest.raises(ApprovalError, match="executed"):
        rt.approve(pa.id, "user:test")  # bấm hai lần không gửi hai lần
    assert len(rt.email_provider.sent) == 1


def test_reject_does_nothing(rt):
    with session_scope(rt.session_factory) as s:
        tx = FinanceService(s, today=lambda: NOW.date()).add_transaction(45000, "an_uong")
    r = run_tool(rt, "finance", "delete_transaction", {"transaction_id": tx.id})
    pa = rt.approvals.get(r.output["approval_id"])
    assert "45.000đ" in pa.summary and "Ăn uống" in pa.summary
    assert rt.reject(pa.id, "user:test", "bấm nhầm").status == "rejected"
    with session_scope(rt.session_factory) as s:
        assert len(FinanceService(s).list_transactions()) == 1


def test_expired_request_cannot_be_approved(session_factory):
    store = ApprovalStore(session_factory, ttl_hours=-1)  # hết hạn ngay khi tạo
    pa = store.create("delete_event", {"event_id": 1}, agent="schedule")
    with pytest.raises(ApprovalError, match="expired"):
        store.approve(pa.id, "user:test", {})


def test_audit_records_writes_and_decisions(rt):
    run_tool(rt, "finance", "add_transaction", {"amount_vnd": 45000, "category": "an_uong"})
    run_tool(rt, "finance", "get_summary", {"period": "today"})  # read → không audit
    actions = [e.action for e in AuditLog(rt.session_factory).recent()]
    assert actions == ["tool:add_transaction"]


def test_kill_switch_denies_agent_tools(rt, tmp_path):
    rt.policy = PolicyProvider(tmp_path / "p.yaml")
    (tmp_path / "p.yaml").write_text("disabled_agents: [finance]\n", encoding="utf-8")
    r = run_tool(rt, "finance", "add_transaction", {"amount_vnd": 45000, "category": "an_uong"})
    assert r.is_error and "kill switch" in r.output
    assert not rt.agent_enabled("finance") and rt.agent_enabled("schedule")


# ---------- CLI: lệnh gọi đúng hàm với đúng tham số ----------

@pytest.mark.parametrize(("argv", "fn", "expected"), [
    (["chat", "--agent", "finance", "--quiet"], "cmd_chat", ("finance", True)),
    (["chat"], "cmd_chat", (None, False)),
    (["approve", "7"], "cmd_decide", (7,)),
    (["summary", "last_month"], "cmd_summary", ("last_month",)),
])
def test_cli_dispatch(monkeypatch, argv, fn, expected):
    calls = []
    monkeypatch.setattr(cli, fn, lambda *a, **k: calls.append(a))
    monkeypatch.setattr(sys, "argv", ["app.cli", *argv])
    monkeypatch.setattr(sys.stdin, "reconfigure", lambda **k: None, raising=False)
    cli.main()
    assert calls == [expected]
