"""Tracer — ghi lại MỌI THỨ agent đã làm trong một lần chạy (run).

Một sự kiện được gửi tới nhiều "sink" (nơi nhận):
  - JsonlSink   mỗi run một file JSONL (bước 2) — đọc nhanh bằng editor
  - ConsoleSink in Thought/Action/Observation ra terminal
  - DbTraceSink lưu vào DB (bước 6, store.py) — để thống kê, trang Agent Runs
  - (bước 14) SSE sink phát realtime lên website
Giao diện `tracer.event(...)` không đổi khi thêm sink → vòng ReAct không phải sửa.

Các loại sự kiện:
  run_start     agent, prompt_version, input, system prompt, danh sách tool, model, parent_run_id
  llm_request   step, toàn bộ history gửi đi (CHÍNH XÁC những gì model nhận được)
  llm_response  step, thoughts, text, tool_calls, usage, latency
  tool_call     step, name, risk, args, status (ok/invalid_args/needs_approval/timeout/...), output, latency
  run_end       status, answer, tổng usage, số bước, error
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

# Asia/Ho_Chi_Minh không có giờ mùa hè → offset +7 cố định (tránh phụ thuộc tzdata trên Windows).
VN_TZ = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")


def to_jsonable(obj: Any) -> Any:
    """Chuyển object bất kỳ (pydantic của SDK, dataclass, ...) sang dạng JSON được."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    return str(obj)


class TraceSink(Protocol):
    def write(self, record: dict[str, Any]) -> None: ...


class Tracer:
    def __init__(
        self,
        directory: Path | None = None,
        console: bool = False,
        sinks: Iterable[TraceSink] = (),
        parent_run_id: str | None = None,
    ) -> None:
        now = datetime.now(VN_TZ)
        # Tên bắt đầu bằng thời gian → sắp xếp theo tên cũng là theo thời gian.
        self.run_id = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.parent_run_id = parent_run_id
        self.directory = directory
        self.path: Path | None = None
        self.extra_sinks = list(sinks)
        self.sinks: list[TraceSink] = []
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
            self.path = directory / f"{self.run_id}.jsonl"
            self.sinks.append(JsonlSink(self.path))
        if console:
            self.sinks.append(ConsoleSink(indent="    " if parent_run_id else ""))
        self.sinks.extend(self.extra_sinks)

    def child(self) -> Tracer:
        """Tracer cho run con (sub-agent): cùng nơi lưu, liên kết bằng parent_run_id."""
        console = any(isinstance(s, ConsoleSink) for s in self.sinks)
        return Tracer(self.directory, console, self.extra_sinks, parent_run_id=self.run_id)

    def event(self, type_: str, **data: Any) -> None:
        if not self.sinks:
            return
        record = {"ts": datetime.now(VN_TZ).isoformat(timespec="milliseconds"), "run_id": self.run_id,
                  "type": type_, **data}
        if type_ == "run_start":
            record["parent_run_id"] = self.parent_run_id
        # Chuyển sang JSON thuần MỘT lần — mọi sink nhận cùng dữ liệu đã chuẩn hoá.
        record = json.loads(json.dumps(record, default=to_jsonable, ensure_ascii=False))
        for sink in self.sinks:
            sink.write(record)


class JsonlSink:
    """Ghi nối từng dòng: run crash giữa chừng vẫn còn các dòng trước."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class ConsoleSink:
    """In theo ngôn ngữ ReAct cho người đọc; bản đầy đủ nằm ở JSONL/DB."""

    def __init__(self, indent: str = "") -> None:
        self.i = indent

    def write(self, r: dict[str, Any]) -> None:
        i, t = self.i, r["type"]
        if t == "run_start":
            tools = ", ".join(x["name"] for x in r.get("tools", []))
            agent = f"{r['agent']} · " if r.get("agent") else ""
            print(f"{i}▶ RUN {r['run_id']} · {agent}model={r.get('model')} · tools=[{tools}]")
            print(f"{i}  USER: {_short(r.get('input', ''), 300)}")
        elif t == "llm_response":
            u = r["usage"]
            print(f"\n{i}── Bước {r['step']} · {r['latency_ms']} ms · tokens in={u['input_tokens']} "
                  f"out={u['output_tokens']} thinking={u['thinking_tokens']}")
            for thought in r["thoughts"]:
                print(f"{i}  [THOUGHT]     {_short(thought, 400)}")
            for call in r["tool_calls"]:
                print(f"{i}  [ACTION]      {call['name']}({json.dumps(call['args'], ensure_ascii=False)})")
            if r["text"]:
                print(f"{i}  [ANSWER]      {r['text']}")
        elif t == "tool_call":
            blocked = r.get("status") in ("needs_approval", "pending_approval", "denied")
            mark = "⛔ " if blocked else "❌ " if r["is_error"] else ""
            print(f"{i}  [OBSERVATION] {mark}{_short(str(r['output']), 300)}  ({r['latency_ms']} ms)")
        elif t == "run_end":
            u = r["usage"]
            if r.get("error"):
                print(f"{i}  ❌ {_short(r['error'], 200)}")
            print(f"\n{i}■ {r['status'].upper()} sau {r['steps']} bước · tổng tokens in={u['input_tokens']} "
                  f"out={u['output_tokens']} thinking={u['thinking_tokens']}")


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
