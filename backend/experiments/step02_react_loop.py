"""Bước 2 — Vòng ReAct + tracer với Gemini thật.

Câu hỏi cố ý cần NHIỀU bước: lấy ngày hôm nay → đếm số ngày → nhân tiền.
Model phải tự lên kế hoạch, gọi tool theo thứ tự, đọc Observation rồi mới gọi tiếp.

Chạy từ thư mục gốc dự án:
    .\\.venv\\Scripts\\python.exe backend\\experiments\\step02_react_loop.py ["câu hỏi khác"]
Trace đầy đủ: backend/data/traces/<run_id>.jsonl (không commit).
"""

import ast
import operator
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from app.harness.agentops.tracer import VN_TZ, Tracer
from app.harness.orchestration.llm_client import GeminiClient, ToolSpec
from app.harness.orchestration.react_loop import Tool, run_react

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")

SYSTEM = """Bạn là trợ lý cá nhân, trả lời bằng tiếng Việt, ngắn gọn.
- Không tự đoán ngày giờ hay tự tính nhẩm: dùng tool, vì đoán sai sẽ làm người dùng quyết định sai.
- Tiền viết dạng 45.000đ."""

QUESTION = (
    "Hôm nay là ngày mấy? Còn bao nhiêu ngày nữa đến Tết Dương lịch 2027, "
    "và nếu từ hôm nay mỗi ngày tôi tiết kiệm 85k thì đến hôm đó tôi có bao nhiêu tiền?"
)


# ---------- 3 tool demo (bước 3 sẽ chuyển sang Tool Registry) ----------

def get_current_time() -> str:
    return datetime.now(VN_TZ).strftime("%A %d/%m/%Y %H:%M (Asia/Ho_Chi_Minh)")


def days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg}


def calculate(expression: str) -> float | int:
    """Máy tính an toàn: chỉ số và + - * / // % ** ( ). KHÔNG dùng eval() — model có thể gửi code bất kỳ."""
    def walk(node: ast.AST) -> float | int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.operand))
        raise ValueError(f"Biểu thức không hợp lệ: {ast.unparse(node)!r}. Chỉ dùng số và + - * / ( ).")
    return walk(ast.parse(expression, mode="eval").body)


TOOLS = [
    Tool(ToolSpec("get_current_time",
                  "Lấy ngày giờ hiện tại ở Việt Nam. Dùng khi câu trả lời cần biết hôm nay.",
                  {"type": "object", "properties": {}}), get_current_time),
    Tool(ToolSpec("days_between", "Đếm số ngày từ ngày start đến ngày end (end - start).",
                  {"type": "object",
                   "properties": {"start": {"type": "string", "description": "YYYY-MM-DD"},
                                  "end": {"type": "string", "description": "YYYY-MM-DD"}},
                   "required": ["start", "end"]}), days_between),
    Tool(ToolSpec("calculate", "Tính một biểu thức số học. Chỉ chấp nhận số thuần (85000, không phải 85k).",
                  {"type": "object",
                   "properties": {"expression": {"type": "string", "description": "vd. (12 + 3) * 85000"}},
                   "required": ["expression"]}), calculate),
]


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    tracer = Tracer(directory=ROOT / "backend" / "data" / "traces", console=True)
    result = run_react(GeminiClient(), SYSTEM, question, TOOLS, max_steps=6, tracer=tracer)
