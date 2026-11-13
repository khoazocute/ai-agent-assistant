# Supervisor Agent — agent card
> Spec cho **người đọc**. Model đọc [`prompt.md`](prompt.md). Code: [`agent.py`](agent.py).

| Mục | Nội dung |
|---|---|
| Mục tiêu | Hiểu yêu cầu, chia nhỏ nếu liên miền, giao cho đúng agent, tổng hợp câu trả lời |
| Mẫu thiết kế | **Agent-as-tool**: mỗi sub-agent là một tool; run con liên kết bằng `parent_run_id` |
| Giới hạn | Không gọi trực tiếp tool nghiệp vụ; độ sâu ủy quyền tối đa 1 tầng |
| Model | `GEMINI_MODEL` — ADR-0002 |
| Ghi chú | Có hay không có Supervisor được quyết định bằng benchmark single vs multi (ADR-0008, bước 9) |

## Tools
| Tool | Risk |
|---|---|
| `ask_finance_agent(request)`, `ask_schedule_agent(request)`, `ask_email_agent(request)` | read (sub-agent tự kiểm soát rủi ro của nó) |
| `recall_facts`, `remember_fact` | read / write |

## KPI
- ≥ 95% định tuyến đúng agent
- Ca liên miền: gọi đủ các agent cần thiết, không gọi thừa
