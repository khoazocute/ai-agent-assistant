"""Tool Registry — tool là một HỢP ĐỒNG API giữa model và code.

Bước 2 viết tay JSON schema cho từng tool → schema và hàm Python dễ lệch nhau (đổi tên tham số ở hàm
mà quên sửa schema). Ở đây MỘT nguồn sự thật là chữ ký hàm:

    @agent_tool(risk=Risk.READ)
    def days_between(start: Annotated[date, Field(description="Ngày bắt đầu")], end: date) -> int:
        '''Đếm số ngày từ start đến end.'''        ← docstring = description model đọc

    → schema JSON cho model (sinh từ type hint bằng pydantic)
    → model pydantic để KIỂM TRA tham số model gửi về trước khi chạy
    → mức rủi ro để executor/policy quyết định có được chạy ngay không

Không có registry toàn cục: mỗi agent tự tạo ToolRegistry với đúng bộ tool của nó (least privilege).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, create_model

from app.harness.orchestration.llm_client import ToolSpec


class Risk(StrEnum):
    READ = "read"  # chỉ đọc → chạy ngay
    WRITE = "write"  # ghi dữ liệu của mình, sửa lại được → chạy ngay (bước 11: + audit)
    DESTRUCTIVE = "destructive"  # xoá / khó hoàn tác → phải có người duyệt
    EXTERNAL = "external"  # tác động ra ngoài (gửi mail) → không thu hồi được → luôn duyệt


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    risk: Risk
    timeout_s: float
    fn: Callable[..., Any]
    args_model: type[BaseModel]
    # Mô tả cho NGƯỜI DUYỆT (bước 11): nhận cùng tham số với fn, trả câu mô tả điều sẽ xảy ra.
    describe: Callable[..., str] | None = None

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, _clean_schema(self.args_model.model_json_schema()))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Vẫn gọi được như hàm thường — service/test không cần đi qua executor.
        return self.fn(*args, **kwargs)


def agent_tool(
    *, risk: Risk, name: str | None = None, timeout_s: float = 10.0, describe: Callable[..., str] | None = None
) -> Callable[[Callable[..., Any]], RegisteredTool]:
    """Biến một hàm có type hint + docstring thành tool. Lỗi khai báo bị báo NGAY lúc import."""

    def decorator(fn: Callable[..., Any]) -> RegisteredTool:
        tool_name = name or fn.__name__
        description = inspect.getdoc(fn)
        if not description:
            # Model chỉ thấy mô tả, không thấy code: tool không mô tả = tool model không biết dùng khi nào.
            raise TypeError(f"Tool '{tool_name}' thiếu docstring — đó chính là mô tả model đọc.")

        hints = get_type_hints(fn, include_extras=True)
        fields: dict[str, Any] = {}
        for param in inspect.signature(fn).parameters.values():
            if param.name not in hints:
                raise TypeError(f"Tool '{tool_name}': tham số '{param.name}' thiếu type hint.")
            default = ... if param.default is inspect.Parameter.empty else param.default
            fields[param.name] = (hints[param.name], default)

        # extra="forbid": model bịa thêm tham số → bị từ chối, không lặng lẽ bỏ qua.
        args_model = create_model(f"{tool_name}_args", __config__=ConfigDict(extra="forbid"), **fields)
        return RegisteredTool(tool_name, description, risk, timeout_s, fn, args_model, describe)

    return decorator


class ToolRegistry:
    def __init__(self, tools: Iterable[RegisteredTool] = ()) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: RegisteredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Trùng tên tool: '{tool.name}'")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def tools(self) -> list[RegisteredTool]:
        return list(self._tools.values())

    @classmethod
    def merge(cls, *registries: ToolRegistry) -> ToolRegistry:
        """Gộp nhiều bộ tool (vd. single-agent). Trùng tên → lỗi ngay, không âm thầm ghi đè."""
        return cls(t for r in registries for t in r.tools())

    def specs(self) -> list[ToolSpec]:
        # Thứ tự xác định (theo thứ tự đăng ký) → prompt giống hệt nhau giữa các lần gọi (tốt cho cache).
        return [t.spec for t in self._tools.values()]


def _clean_schema(schema: Any) -> Any:
    """Bỏ các khoá 'title' pydantic tự thêm: model không cần, chỉ tốn token mỗi lần gọi.
    Cẩn thận: bên trong "properties" thì khoá là TÊN THAM SỐ (vd. tham số tên `title`) — giữ nguyên."""
    if isinstance(schema, list):
        return [_clean_schema(v) for v in schema]
    if not isinstance(schema, dict):
        return schema
    cleaned = {}
    for key, value in schema.items():
        if key == "title" and isinstance(value, str):
            continue
        if key in ("properties", "$defs") and isinstance(value, dict):
            cleaned[key] = {name: _clean_schema(sub) for name, sub in value.items()}
        else:
            cleaned[key] = _clean_schema(value)
    return cleaned
