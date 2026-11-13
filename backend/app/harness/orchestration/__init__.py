"""Orchestration Harness — điều phối vòng lặp và các agent.

- llm_client.py  giao diện trung lập + adapter Gemini: thinking, timeout, retry   (bước 2, ADR-0002/0003)
- react_loop.py  vòng ReAct thủ công: Thought → Action → Observation             (bước 2)
- supervisor.py  router agent-as-tool, so sánh single vs multi                   (bước 8–9)
- approvals.py   vòng đời PendingAction: pending → approved/rejected → executed   (bước 11)
"""
