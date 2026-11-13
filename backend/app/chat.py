"""ChatService — xử lý MỘT tin nhắn của người dùng, không phụ thuộc kênh (Telegram, web, CLI).

    tin nhắn → kiểm tra agent có bật → lấy memory ngắn hạn → agent.run (trace vào DB)
             → lưu lượt hội thoại → gom yêu cầu duyệt mới phát sinh → trả lời

Kênh chỉ lo phần hiển thị (nút bấm Telegram, giao diện web) — logic nằm ở đây, test được không cần mạng.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.harness.context.memory import ConversationMemory
from app.harness.evaluation.feedback import FeedbackStore
from app.harness.orchestration.approvals import PendingAction
from app.runtime import Runtime

_VN = timezone(timedelta(hours=7))


@dataclass
class ChatReply:
    answer: str
    run_id: str = ""
    status: str = "ok"
    tools_used: list[str] = field(default_factory=list)
    approvals: list[PendingAction] = field(default_factory=list)  # yêu cầu duyệt vừa được tạo trong lượt này


class ChatService:
    def __init__(self, runtime: Runtime, agent_name: str | None = None) -> None:
        self.rt = runtime
        self.agent_name = agent_name
        self.memory = ConversationMemory(runtime.session_factory)
        self.feedback = FeedbackStore(runtime.session_factory)

    def handle(self, channel: str, external_id: str, text: str) -> ChatReply:
        agent = self.rt.agent(self.agent_name)
        if not self.rt.agent_enabled(agent.name):
            return ChatReply("Trợ lý đang tạm tắt (kill switch trong config/policies.yaml).", status="disabled")

        conv = self.memory.conversation_id(channel, external_id)
        started = datetime.now(_VN).replace(tzinfo=None) - timedelta(seconds=1)
        tracer = self.rt.tracer(channel)
        try:
            result = agent.run(text, tracer, history=self.memory.recent(conv), meta={"channel": channel})
        except Exception as e:  # lỗi model sau khi đã retry: báo lịch sự, trace đã ghi status=error
            quota = getattr(e, "code", None) == 429
            msg = ("Hết lượt gọi AI hôm nay (quota Gemini). Thử lại sau nhé." if quota
                   else "Xin lỗi, trợ lý đang gặp sự cố khi gọi AI. Thử lại sau ít phút nhé.")
            return ChatReply(msg, run_id=tracer.run_id, status="error")

        self.memory.append(conv, "user", text, tracer.run_id)
        self.memory.append(conv, "assistant", result.answer, tracer.run_id)
        new_approvals = [pa for pa in self.rt.approvals.list("pending") if pa.created_at >= started]
        return ChatReply(result.answer, tracer.run_id, result.status,
                         [c.name for c in result.tool_calls], sorted(new_approvals, key=lambda p: p.id))

    def reset(self, channel: str, external_id: str) -> None:
        self.memory.reset(self.memory.conversation_id(channel, external_id))
