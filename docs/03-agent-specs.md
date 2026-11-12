# 03 — Đặc tả agent
Mỗi agent có agent card riêng (spec cho người đọc), nằm cạnh code:

| Agent | Card | Loại |
|---|---|---|
| Supervisor | [AGENT.md](../backend/app/agents/supervisor/AGENT.md) | ReAct, agent-as-tool |
| Finance | [AGENT.md](../backend/app/agents/finance/AGENT.md) | ReAct |
| Schedule | [AGENT.md](../backend/app/agents/schedule/AGENT.md) | ReAct + planner xác định |
| Email | [AGENT.md](../backend/app/agents/email/AGENT.md) | ReAct + duyệt bắt buộc |
| Briefing | [AGENT.md](../backend/app/agents/briefing/AGENT.md) | Workflow (1 lần gọi LLM) |
