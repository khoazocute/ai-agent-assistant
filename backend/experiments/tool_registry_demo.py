"""Bước 3 — Tool Registry + Executor: tool là một hợp đồng API.

Ba phần:
  1. In schema mà model THẤY — sinh tự động từ type hint + docstring (không viết tay).
  2. Gọi executor trực tiếp với tham số sai / tool rủi ro cao → xem Observation lỗi (không cần LLM).
  3. Run thật với Gemini: yêu cầu xoá dữ liệu → executor CHẶN vì risk=destructive, dù model muốn gọi.

Chạy từ thư mục gốc dự án:
    .\\.venv\\Scripts\\python.exe backend\\experiments\\tool_registry_demo.py
"""

import json
import sys
from pathlib import Path

from demo_tools import SYSTEM, demo_registry
from dotenv import load_dotenv

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import GeminiClient, ToolCall
from app.harness.orchestration.react_loop import run_react
from app.harness.tools.executor import ToolExecutor

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")

registry = demo_registry()
executor = ToolExecutor(registry)

print("=== 1. Schema model nhìn thấy (sinh từ type hint) ===")
for name in ("days_between", "delete_all_savings_notes"):
    tool = registry.get(name)
    print(f"\n[{tool.risk}] {name}: {tool.description}")
    print(json.dumps(tool.spec.parameters, ensure_ascii=False, indent=2))

print("\n=== 2. Executor chặn trước khi tool chạy (không cần LLM) ===")
cases = [
    ToolCall("a", "days_between", {"start": "2026-11-13", "end": "2027-01-01"}),
    ToolCall("b", "days_between", {"start": "13/11/2026", "end": "2027-01-01"}),
    ToolCall("c", "days_between", {"start": "2026-11-13", "end": "2027-01-01", "inclusive": True}),
    ToolCall("d", "calculate", {"expression": "__import__('os').system('dir')"}),
    ToolCall("e", "delete_all_savings_notes", {}),
]
for call in cases:
    r = executor.execute(call)
    print(f"  {'❌' if r.is_error else '✅'} {call.name}({json.dumps(call.args, ensure_ascii=False)})\n"
          f"     → {r.output}")

print("\n=== 3. Run thật: model muốn xoá dữ liệu ===")
tracer = Tracer(directory=ROOT / "backend" / "data" / "traces", console=True)
run_react(GeminiClient(), SYSTEM, "Xoá hết ghi chú tiết kiệm của tôi đi.", executor, tracer=tracer)
