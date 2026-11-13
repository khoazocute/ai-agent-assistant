"""Test Tool Harness: schema sinh từ type hint, kiểm tra tham số, mức rủi ro, timeout, rút gọn output."""

import time
from datetime import date
from typing import Annotated, Literal

import pytest
from pydantic import Field

from app.harness.orchestration.llm_client import ToolCall
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool


@agent_tool(risk=Risk.READ)
def days_between(
    start: Annotated[date, Field(description="Ngày bắt đầu")],
    end: Annotated[date, Field(description="Ngày kết thúc")],
) -> int:
    """Đếm số ngày từ start đến end."""
    return (end - start).days


@agent_tool(risk=Risk.WRITE)
def create_event(title: str, kind: Literal["work", "study"] = "work") -> str:
    """Tạo sự kiện (tham số tên `title` — để kiểm tra schema không bị xoá nhầm)."""
    return f"created {title} ({kind})"


@agent_tool(risk=Risk.EXTERNAL)
def send_email(to: str, body: str) -> str:
    """Gửi email."""
    raise AssertionError("KHÔNG BAO GIỜ được chạy khi chưa duyệt")


@agent_tool(risk=Risk.READ, timeout_s=0.1)
def slow() -> str:
    """Tool chậm."""
    time.sleep(1)
    return "xong"


@agent_tool(risk=Risk.READ)
def huge() -> str:
    """Trả về rất nhiều dữ liệu."""
    return "x" * 10_000


EXECUTOR = ToolExecutor(ToolRegistry([days_between, create_event, send_email, slow, huge]))


def run(name: str, **args):
    return EXECUTOR.execute(ToolCall("id1", name, args))


# ---------- Registry: schema ----------

def test_schema_comes_from_type_hints_and_docstring():
    spec = days_between.spec
    assert spec.description == "Đếm số ngày từ start đến end."
    assert spec.parameters["required"] == ["start", "end"]
    assert spec.parameters["properties"]["start"] == {
        "type": "string", "format": "date", "description": "Ngày bắt đầu",
    }
    assert spec.parameters["additionalProperties"] is False


def test_schema_drops_pydantic_titles_but_keeps_param_named_title():
    params = create_event.spec.parameters
    assert "title" not in params  # 'title' tự sinh của pydantic → bỏ
    assert "title" in params["properties"]  # tham số tên title → giữ
    assert params["properties"]["kind"] == {"type": "string", "enum": ["work", "study"], "default": "work"}
    assert params["required"] == ["title"]


def test_tool_without_docstring_or_type_hint_fails_at_definition():
    with pytest.raises(TypeError, match="docstring"):
        @agent_tool(risk=Risk.READ)
        def no_doc(x: int) -> int:
            return x

    with pytest.raises(TypeError, match="type hint"):
        @agent_tool(risk=Risk.READ)
        def no_hint(x) -> int:
            """Có docstring nhưng thiếu type hint."""
            return x


def test_registry_rejects_duplicate_names():
    with pytest.raises(ValueError, match="Trùng"):
        ToolRegistry([days_between, days_between])


def test_decorated_tool_is_still_a_plain_function():
    assert days_between(date(2026, 1, 1), date(2026, 1, 31)) == 30


# ---------- Executor ----------

def test_valid_args_are_converted_to_python_types():
    result = run("days_between", start="2026-11-13", end="2027-01-01")
    assert (result.output, result.is_error) == (49, False)  # chuỗi → date trước khi vào hàm


def test_invalid_args_explain_which_field_is_wrong():
    result = run("days_between", start="13/11/2026", end="2027-01-01")
    assert result.is_error
    assert "start" in result.output and "Hãy gọi lại" in result.output


def test_extra_and_missing_args_are_rejected():
    result = run("days_between", start="2026-11-13", end="2027-01-01", note="bịa thêm")
    assert result.is_error and "note" in result.output
    assert run("days_between", start="2026-11-13").is_error


def test_enum_is_enforced():
    assert run("create_event", title="Họp", kind="party").is_error
    assert run("create_event", title="Học").output == "created Học (work)"


def test_external_tool_never_runs_without_approval():
    result = run("send_email", to="a@b.com", body="hi")  # AssertionError bên trong sẽ lộ ra nếu chạy
    assert result.is_error and "cần người dùng duyệt" in result.output


def test_unknown_tool_lists_available_tools():
    result = run("delete_everything")
    assert result.is_error and "days_between" in result.output


def test_timeout_does_not_hang_the_run():
    start = time.perf_counter()
    result = run("slow")
    assert result.is_error and "quá thời gian" in result.output
    assert time.perf_counter() - start < 0.5


def test_huge_output_is_truncated_and_says_so():
    result = run("huge")
    assert not result.is_error
    assert len(result.output) < 4_200 and "đã cắt" in result.output
