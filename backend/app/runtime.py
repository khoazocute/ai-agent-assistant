"""Runtime — dựng MỘT lần mọi thứ dùng chung: DB, LLM, policy, duyệt, audit, email, danh mục tool.

CLI, Telegram, web API và job nền đều đi qua đây → cùng một policy, cùng một kho duyệt, cùng audit.
Mọi agent được dựng với executor "có quản trị" (policy + duyệt + audit) — không có đường tắt bỏ qua policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.base import BaseAgent
from app.bootstrap import make_llm, make_tracer, setup_database
from app.config import CONFIG_DIR, get_settings, now_vn
from app.db.session import SessionFactory
from app.harness.agentops.tracer import Tracer
from app.harness.governance.audit import AuditLog
from app.harness.governance.policy_engine import PolicyProvider
from app.harness.orchestration.approvals import ApprovalStore, PendingAction
from app.harness.orchestration.llm_client import LLMClient
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import RegisteredTool, ToolRegistry
from app.integrations.email_provider import EmailProvider
from app.realtime import EventBus, install_change_listener


@dataclass
class Runtime:
    session_factory: SessionFactory
    policy: PolicyProvider
    audit: AuditLog
    approvals: ApprovalStore
    email_provider: EmailProvider
    _llm: LLMClient | None = field(default=None, repr=False)
    bus: EventBus = field(default_factory=EventBus)

    @classmethod
    def create(cls, db_url: str | None = None, email_provider: EmailProvider | None = None,
               llm: LLMClient | None = None) -> Runtime:
        from app.agents.registry import default_email_provider

        factory = setup_database(db_url)
        policy = PolicyProvider(CONFIG_DIR / "policies.yaml")
        audit = AuditLog(factory)
        approvals = ApprovalStore(factory, audit, ttl_hours=policy.get().approval_ttl_hours)
        rt = cls(factory, policy, audit, approvals, email_provider or default_email_provider(), llm)
        install_change_listener(factory, rt.bus)  # mọi commit DB → sự kiện realtime cho website
        return rt

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = make_llm()
        return self._llm

    def make_executor(self, registry: ToolRegistry) -> ToolExecutor:
        return ToolExecutor(registry, policy=self.policy, approvals=self.approvals, audit=self.audit)

    def agent(self, name: str | None = None, now: Any = now_vn) -> BaseAgent:
        from app.agents.registry import build_agent

        return build_agent(name or get_settings().default_agent, self.llm, self.session_factory, now,
                           self.make_executor, self.email_provider)

    def agent_enabled(self, name: str) -> bool:
        return self.policy.get().agent_enabled(name)

    def tracer(self, channel: str, console: bool = False) -> Tracer:
        return make_tracer(self.session_factory, channel, console)

    def tool_catalog(self) -> dict[str, RegisteredTool]:
        """Mọi tool nghiệp vụ theo tên — để thực thi một yêu cầu đã được duyệt."""
        from app.agents.email.tools import build_email_tools
        from app.agents.finance.tools import build_finance_tools
        from app.agents.schedule.tools import build_schedule_tools

        merged = ToolRegistry.merge(build_finance_tools(self.session_factory),
                                    build_schedule_tools(self.session_factory),
                                    build_email_tools(self.session_factory, self.email_provider))
        return {t.name: t for t in merged.tools()}

    def approve(self, action_id: int, actor: str) -> PendingAction:
        return self.approvals.approve(action_id, actor, self.tool_catalog())

    def reject(self, action_id: int, actor: str, reason: str = "") -> PendingAction:
        return self.approvals.reject(action_id, actor, reason)
