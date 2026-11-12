"""Tool Harness — tool là một hợp đồng API giữa model và code.

- registry.py  decorator @agent_tool(risk=...), schema pydantic, strict: true      (bước 3)
- executor.py  validate → hỏi policy → chạy (timeout/retry) → chuẩn hoá lỗi → trace (bước 3, 11)
Mức rủi ro: read | write | destructive | external.
"""
