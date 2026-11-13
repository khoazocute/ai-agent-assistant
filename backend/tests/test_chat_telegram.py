"""ChatService (memory, duyệt, phản hồi) + các hàm định dạng của bot Telegram — không cần mạng."""

from datetime import datetime

import pytest
from conftest import NOW
from fakes import FakeLLM

from app.chat import ChatReply, ChatService
from app.harness.context.memory import ConversationMemory, UserFacts
from app.harness.orchestration.approvals import PendingAction
from app.harness.orchestration.llm_client import ToolCall
from app.integrations.email_provider import FakeEmailProvider
from app.integrations.telegram_bot import format_approval, format_reply, is_allowed, md_to_html, parse_callback
from app.runtime import Runtime


def runtime(script) -> Runtime:
    return Runtime.create("sqlite://", email_provider=FakeEmailProvider(), llm=FakeLLM(script))


def test_memory_carries_previous_turns_into_next_message():
    rt = runtime(["Đã ghi nhận.", "Đã dời."])
    chat = ChatService(rt, agent_name="finance")
    chat.handle("telegram", "42", "trưa nay ăn phở 45k")
    chat.handle("telegram", "42", "à nhầm, 50k chứ")
    second_call = rt.llm.seen_histories[1]
    assert [m["role"] for m in second_call] == ["user", "model", "user"]
    assert second_call[0]["text"] == "trưa nay ăn phở 45k" and second_call[1]["text"] == "Đã ghi nhận."



def test_memory_is_per_conversation_and_resettable(session_factory):
    mem = ConversationMemory(session_factory, max_turns=4)
    a, b = mem.conversation_id("telegram", "1"), mem.conversation_id("telegram", "2")
    assert mem.conversation_id("telegram", "1") == a and a != b
    for i in range(5):
        mem.append(a, "user", f"tin {i}")
    assert [t for _, t in mem.recent(a)] == ["tin 1", "tin 2", "tin 3", "tin 4"]  # chỉ N lượt gần nhất
    assert mem.recent(b) == []
    mem.reset(a)
    assert mem.recent(a) == []


def test_user_facts(session_factory):
    facts = UserFacts(session_factory)
    facts.remember("Giờ đi ngủ", "23h")
    facts.remember("giờ đi ngủ", "23h30")  # cùng khoá (không phân biệt hoa thường) → cập nhật
    assert facts.all() == {"giờ đi ngủ": "23h30"}
    assert facts.forget("giờ đi ngủ") and facts.all() == {}


def test_reply_includes_approvals_created_in_this_turn():
    rt = runtime([
        [ToolCall("d", "delete_event", {"event_id": 1})], "Đã tạo yêu cầu duyệt, chưa xoá.",
    ])
    from app.db.session import session_scope
    from app.services.schedule_service import ScheduleService

    with session_scope(rt.session_factory) as s:
        ScheduleService(s, now=lambda: NOW).create_event("Họp", datetime(2026, 11, 14, 9), duration_min=60)
    reply = ChatService(rt, agent_name="schedule").handle("telegram", "42", "xoá lịch họp mai")
    assert reply.tools_used == ["delete_event"]
    (pa,) = reply.approvals
    assert pa.tool == "delete_event" and "Họp" in pa.summary


def test_model_error_gives_friendly_message_not_crash():
    class Quota(FakeLLM):
        def generate(self, *a):
            e = RuntimeError("429")
            e.code = 429
            raise e

    rt = Runtime.create("sqlite://", email_provider=FakeEmailProvider(), llm=Quota([]))
    reply = ChatService(rt, agent_name="finance").handle("telegram", "1", "hi")
    assert reply.status == "error" and "quota" in reply.answer


def test_disabled_agent(tmp_path):
    from app.harness.governance.policy_engine import PolicyProvider

    rt = runtime([])
    rt.policy = PolicyProvider(tmp_path / "p.yaml")
    (tmp_path / "p.yaml").write_text("disabled_agents: [finance]\n", encoding="utf-8")
    assert ChatService(rt, agent_name="finance").handle("telegram", "1", "hi").status == "disabled"


# ---------- Hàm định dạng Telegram ----------

def test_allowlist_fails_closed():
    assert is_allowed(42, {42}) and not is_allowed(7, {42}) and not is_allowed(42, set())


def test_md_to_html_escapes_before_formatting():
    assert md_to_html("**45.000đ** <script> `x`") == "<b>45.000đ</b> &lt;script&gt; <code>x</code>"


def test_format_reply_shows_tools_and_truncates():
    text = format_reply(ChatReply("x" * 5000, tools_used=["ask_finance_agent", "add_transaction", "add_transaction"]))
    assert len(text) <= 4000 and "đã cắt bớt" in text
    assert "🔧 ask_finance_agent → add_transaction" in format_reply(
        ChatReply("ok", tools_used=["ask_finance_agent", "add_transaction", "add_transaction"]))


def test_format_approval_escapes_untrusted_summary():
    pa = PendingAction(id=3, tool="send_email", summary="Tới: a@b.vn\n<b>hack</b>",
                       expires_at=datetime(2026, 11, 14, 12, 0))
    out = format_approval(pa)
    assert "#3" in out and "&lt;b&gt;hack&lt;/b&gt;" in out


@pytest.mark.parametrize(("data", "expected"), [
    ("ap:12:y", ("ap", "12", "y")),
    ("fb:20261113-230859-469fe1:-1", ("fb", "20261113-230859-469fe1", "-1")),
])
def test_parse_callback(data, expected):
    assert parse_callback(data) == expected


@pytest.mark.parametrize("bad", ["", "xx:1:y", "ap:", "ap:12"])
def test_parse_callback_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_callback(bad)
