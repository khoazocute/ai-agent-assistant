"""Tool demo dùng chung cho các script experiments (bước 2–3). Agent thật có tool riêng từ bước 4."""

import ast
import operator
from datetime import date, datetime
from typing import Annotated

from pydantic import Field

from app.harness.agentops.tracer import VN_TZ
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool

SYSTEM = """Bạn là trợ lý cá nhân, trả lời bằng tiếng Việt, ngắn gọn.
- Không tự đoán ngày giờ hay tự tính nhẩm: dùng tool, vì đoán sai sẽ làm người dùng quyết định sai.
- Tiền viết dạng 45.000đ."""


@agent_tool(risk=Risk.READ)
def get_current_time() -> str:
    """Lấy ngày giờ hiện tại ở Việt Nam. Dùng khi câu trả lời cần biết hôm nay."""
    return datetime.now(VN_TZ).strftime("%A %d/%m/%Y %H:%M (Asia/Ho_Chi_Minh)")


@agent_tool(risk=Risk.READ)
def days_between(
    start: Annotated[date, Field(description="Ngày bắt đầu, dạng YYYY-MM-DD")],
    end: Annotated[date, Field(description="Ngày kết thúc, dạng YYYY-MM-DD")],
) -> int:
    """Đếm số ngày từ ngày start đến ngày end (end - start)."""
    return (end - start).days


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg}


@agent_tool(risk=Risk.READ)
def calculate(
    expression: Annotated[str, Field(description="Biểu thức số học, vd. (12 + 3) * 85000")],
) -> float | int:
    """Tính một biểu thức số học. Chỉ chấp nhận số thuần (85000, không phải 85k)."""
    # KHÔNG dùng eval(): model (hoặc nội dung độc hại model đọc được) có thể gửi code bất kỳ.
    def walk(node: ast.AST) -> float | int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.operand))
        raise ValueError(f"Biểu thức không hợp lệ: {ast.unparse(node)!r}. Chỉ dùng số và + - * / ( ).")
    return walk(ast.parse(expression, mode="eval").body)


@agent_tool(risk=Risk.DESTRUCTIVE)
def delete_all_savings_notes() -> str:
    """Xoá toàn bộ ghi chú tiết kiệm của người dùng. Không hoàn tác được."""
    return "Đã xoá."  # demo: executor sẽ chặn trước khi tới đây


def demo_registry() -> ToolRegistry:
    return ToolRegistry([get_current_time, days_between, calculate, delete_all_savings_notes])
