"""Bước 2 — Vòng ReAct + tracer với Gemini thật.

Câu hỏi cố ý cần NHIỀU bước: lấy ngày hôm nay → đếm số ngày → nhân tiền.
Model phải tự lên kế hoạch, gọi tool theo thứ tự, đọc Observation rồi mới gọi tiếp.
(Từ bước 3, tool khai báo bằng @agent_tool trong demo_tools.py thay vì viết tay JSON schema.)

Chạy từ thư mục gốc dự án:
    .\\.venv\\Scripts\\python.exe backend\\experiments\\react_loop_demo.py ["câu hỏi khác"]
Trace đầy đủ: backend/data/traces/<run_id>.jsonl (không commit).
"""

import sys
from pathlib import Path

from demo_tools import SYSTEM, demo_registry
from dotenv import load_dotenv

from app.harness.agentops.tracer import Tracer
from app.harness.orchestration.llm_client import GeminiClient
from app.harness.orchestration.react_loop import run_react
from app.harness.tools.executor import ToolExecutor

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")

QUESTION = (
    "Hôm nay là ngày mấy? Còn bao nhiêu ngày nữa đến Tết Dương lịch 2027, "
    "và nếu từ hôm nay mỗi ngày tôi tiết kiệm 85k thì đến hôm đó tôi có bao nhiêu tiền?"
)

if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    tracer = Tracer(directory=ROOT / "backend" / "data" / "traces", console=True)
    run_react(GeminiClient(), SYSTEM, question, ToolExecutor(demo_registry()), max_steps=6, tracer=tracer)
