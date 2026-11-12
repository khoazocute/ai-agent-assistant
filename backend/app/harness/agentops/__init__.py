"""AgentOps Harness — nhìn thấy agent đang làm gì, tốn bao nhiêu.

- tracer.py   ghi từng LLM call / tool call: request đầy đủ, response, token, latency
              (bước 2: ra console/JSON; bước 6: vào DB; bước 14: phát realtime qua SSE)
- metrics.py  thành công, p50/p95, $/run, cache hit                      (bước 14)
- alerts.py   cảnh báo qua Telegram khi lỗi hoặc vượt ngân sách          (bước 14)
"""
