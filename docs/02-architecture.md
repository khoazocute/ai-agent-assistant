# 02 — Kiến trúc

## Sơ đồ tổng thể
```
Telegram (polling/webhook) ─┐                         ┌─ ask_finance_agent ─▶ Finance Agent ─▶ FinanceService ──┐
Web React (cookie httpOnly) ─┼─▶ FastAPI ─▶ ChatService ─▶ Supervisor ─┼─ ask_schedule_agent ─▶ Schedule Agent ─▶ ScheduleService ─┼─▶ SQLite / PostgreSQL
CLI                         ─┘      │                         └─ ask_email_agent ─▶ Email Agent ─▶ EmailService ────┘     │
                                    │                                                                                       ├─ Gmail API
APScheduler (bản tin, nhắc lịch, ───┤   Workflow (1 lượt LLM, 0 tool): bản tin · ảnh hóa đơn                                └─ Google Calendar API
đồng bộ, dọn dữ liệu)               └── SSE /api/stream ◀── EventBus ◀── SQLAlchemy after_commit (mọi đường ghi)
```

## Phân lớp và quy tắc phụ thuộc
| Lớp | Thư mục | Được import | Không được import |
|---|---|---|---|
| Harness (7) | `app/harness/` | thư viện ngoài | `agents`, `services`, `integrations`, `db`, `config`, `api` |
| Nghiệp vụ | `app/services/` | `db`, `config`, `harness/security` | `agents`, `api` |
| Agent | `app/agents/<agent>/` | `services`, `harness` | `api` |
| Kênh | `app/api/`, `integrations/telegram_bot.py`, `cli.py` | mọi thứ qua `Runtime` | — |

`app/runtime.py` dựng một lần: DB, LLM, policy, kho duyệt, audit, email, lịch, EventBus → mọi kênh dùng chung, không có đường tắt bỏ qua policy.

## 7 harness
| Harness | File chính | Trách nhiệm |
|---|---|---|
| Context | `context/prompts.py`, `memory.py` | prompt.md + version hash; memory 6 lượt chữ; user_facts |
| Tool | `tools/registry.py`, `executor.py` | schema từ type hint; validate → policy → chạy/tạo duyệt/từ chối → timeout → cắt output → audit |
| Orchestration | `orchestration/llm_client.py`, `react_loop.py`, `approvals.py` | adapter Gemini trung lập; vòng ReAct; PendingAction |
| Evaluation | `evaluation/scorer.py`, `feedback.py` + `backend/evals/` | chấm bằng code; ngưỡng 90% + an toàn 100%; 👍/👎 |
| Security | `security/sanitizer.py`, `pii.py`, `crypto.py`, `auth.py` | untrusted_content, dò injection, PII, Fernet, JWT |
| Governance | `governance/policy_engine.py`, `audit.py` + `config/policies.yaml` | allow/approve/deny, kill switch, luật cứng external, audit |
| AgentOps | `agentops/tracer.py`, `store.py`, `cost.py`, `metrics.py` | sink JSONL/console/DB; chi phí; p50/p95; dọn 90 ngày |

## Luồng một tin nhắn
1. Kênh → `ChatService.handle`: kill switch → memory (6 lượt) → `Supervisor.run` với tracer (DB + JSONL).
2. Supervisor (ReAct) gọi `ask_*_agent(request)` → sub-agent chạy ReAct riêng (run con, `parent_run_id`).
3. Sub-agent gọi tool → `ToolExecutor`: validate → policy → `allow` chạy service · `require_approval` tạo PendingAction · `deny`.
4. Service ghi DB → `after_commit` → EventBus → SSE → web làm mới.
5. Trả lời + yêu cầu duyệt mới (nút ✅/❌) → người dùng duyệt → `Runtime.approve` chạy đúng tool + tham số đã lưu.

## Dữ liệu
Nghiệp vụ (`app/db/models.py`): `categories`, `transactions`, `events`, `tasks`, `schedule_plans`, `emails`, `email_drafts`, `calendar_tombstones`, `sync_state`.
Harness (`HarnessBase`): `agent_runs`, `agent_events`, `pending_actions`, `audit_log`, `conversations`, `conversation_messages`, `user_facts`, `feedback`.

Quyết định: xem [docs/adr/](adr/README.md).
