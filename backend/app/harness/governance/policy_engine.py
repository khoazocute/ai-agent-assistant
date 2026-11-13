"""Policy engine — quyết định một tool có được chạy, phải duyệt, hay bị từ chối (ADR-0010).

Thứ tự xét:
  1. agent bị tắt (disabled_agents) hoặc tool bị tắt (disabled_tools)   → deny   (kill switch)
  2. luật riêng của tool (tools:)                                       → theo YAML
  3. mặc định theo mức rủi ro (defaults:)                               → theo YAML
  4. LUẬT CỨNG: risk=external không bao giờ "allow" — kể cả YAML ghi sai → require_approval
`PolicyProvider` đọc lại file khi nó thay đổi → sửa YAML là có hiệu lực, không cần deploy lại.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import yaml


class Decision(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str


@dataclass
class Policy:
    defaults: dict[str, Decision] = field(default_factory=lambda: {
        "read": Decision.ALLOW, "write": Decision.ALLOW,
        "destructive": Decision.REQUIRE_APPROVAL, "external": Decision.REQUIRE_APPROVAL})
    tools: dict[str, Decision] = field(default_factory=dict)
    disabled_tools: set[str] = field(default_factory=set)
    disabled_agents: set[str] = field(default_factory=set)
    approval_ttl_hours: float = 24

    @classmethod
    def from_dict(cls, raw: dict) -> Policy:
        base = cls()
        return cls(
            defaults={**base.defaults, **{k: Decision(v) for k, v in (raw.get("defaults") or {}).items()}},
            tools={k: Decision(v) for k, v in (raw.get("tools") or {}).items()},
            disabled_tools=set(raw.get("disabled_tools") or []),
            disabled_agents=set(raw.get("disabled_agents") or []),
            approval_ttl_hours=float(raw.get("approval_ttl_hours", 24)),
        )

    @classmethod
    def load(cls, path: Path) -> Policy:
        return cls.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else cls()

    def agent_enabled(self, agent: str) -> bool:
        return agent not in self.disabled_agents

    def decide(self, tool: str, risk: str, agent: str = "") -> PolicyDecision:
        if agent and agent in self.disabled_agents:
            return PolicyDecision(Decision.DENY, f"Agent '{agent}' đang bị tắt (kill switch).")
        if tool.startswith("ask_") and tool.removeprefix("ask_").removesuffix("_agent") in self.disabled_agents:
            return PolicyDecision(Decision.DENY, f"Agent của tool '{tool}' đang bị tắt (kill switch).")
        if tool in self.disabled_tools:
            return PolicyDecision(Decision.DENY, f"Tool '{tool}' đang bị tắt (kill switch).")
        decision = self.tools.get(tool) or self.defaults.get(risk, Decision.REQUIRE_APPROVAL)
        reason = f"luật riêng của tool '{tool}'" if tool in self.tools else f"mặc định cho rủi ro '{risk}'"
        if risk == "external" and decision == Decision.ALLOW:
            # Luật cứng: hành động ra thế giới bên ngoài (không thu hồi được) luôn cần người duyệt.
            return PolicyDecision(Decision.REQUIRE_APPROVAL, "luật cứng: rủi ro 'external' luôn cần duyệt")
        return PolicyDecision(decision, reason)


class PolicyProvider:
    """Trả Policy mới nhất; chỉ đọc lại file khi thời điểm sửa đổi (mtime) thay đổi."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._policy = Policy()

    def get(self) -> Policy:
        mtime = self.path.stat().st_mtime if self.path.exists() else None
        if mtime != self._mtime:
            self._policy, self._mtime = Policy.load(self.path), mtime
        return self._policy
