"""AgentOps Harness — nhìn thấy agent đang làm gì, tốn bao nhiêu.

- tracer.py   Tracer + sink: JSONL, console (bước 2), DB (bước 6), SSE realtime (bước 14)
- store.py    bảng agent_runs + agent_events, DbTraceSink, đọc lại run      (bước 6, ADR-0006)
- cost.py     chi phí từ token × config/pricing.yaml                         (bước 6)
- metrics.py  thành công, p50/p95, token, chi phí theo agent                 (bước 6)
- alerts.py   cảnh báo qua Telegram khi lỗi hoặc vượt ngân sách              (bước 14)
"""
