"""Tracer — ghi lại MỌI THỨ agent đã làm trong một lần chạy (run).

Bước 2: mỗi run là một file JSONL (mỗi dòng = một sự kiện) + tuỳ chọn in đẹp ra console.
Bước 6 sẽ thêm nơi lưu là DB; bước 14 phát realtime qua SSE — giao diện `event(...)` giữ nguyên.

Vì sao JSONL: ghi nối thêm từng dòng (run bị crash giữa chừng vẫn còn các dòng trước),
mở bằng editor là đọc được, và dễ nạp vào DB sau này.

Các loại sự kiện:
  run_start     input, system prompt, danh sách tool, model
  llm_request   step, toàn bộ history gửi đi (CHÍNH XÁC những gì model nhận được)
  llm_response  step, thoughts, text, tool_calls, usage, latency
  tool_call     step, name, risk, args, status (ok/invalid_args/needs_approval/timeout/...), output, latency
  run_end       status, answer, tổng usage, số bước
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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


class Tracer:
    def __init__(self, directory: Path | None = None, console: bool = False) -> None:
        now = datetime.now(VN_TZ)
        # Tên bắt đầu bằng thời gian → sắp xếp theo tên cũng là theo thời gian.
        self.run_id = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.console = console
        self.path: Path | None = None
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
            self.path = directory / f"{self.run_id}.jsonl"

    def event(self, type_: str, **data: Any) -> None:
        record = {"ts": datetime.now(VN_TZ).isoformat(timespec="milliseconds"), "run_id": self.run_id,
                  "type": type_, **data}
        if self.path is not None:
            line = json.dumps(record, default=to_jsonable, ensure_ascii=False)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        if self.console:
            self._print(type_, data)

    # ---- In theo ngôn ngữ ReAct cho người đọc; file JSONL mới là bản đầy đủ ----
    def _print(self, type_: str, d: dict[str, Any]) -> None:
        if type_ == "run_start":
            tools = ", ".join(t.name for t in d.get("tools", []))
            print(f"▶ RUN {self.run_id} · model={d.get('model')} · tools=[{tools}]")
            print(f"  USER: {d.get('input')}")
        elif type_ == "llm_response":
            u = d["usage"]
            print(f"\n── Bước {d['step']} · {d['latency_ms']} ms · tokens in={u.input_tokens} "
                  f"out={u.output_tokens} thinking={u.thinking_tokens}")
            for thought in d["thoughts"]:
                print(f"  [THOUGHT]     {_short(thought, 400)}")
            for call in d["tool_calls"]:
                print(f"  [ACTION]      {call.name}({json.dumps(call.args, ensure_ascii=False)})")
            if d["text"]:
                print(f"  [ANSWER]      {d['text']}")
        elif type_ == "tool_call":
            status = d.get("status")
            mark = "⛔ " if status == "needs_approval" else "❌ " if d["is_error"] else ""
            print(f"  [OBSERVATION] {mark}{_short(str(d['output']), 300)}  ({d['latency_ms']} ms)")
        elif type_ == "run_end":
            u = d["usage"]
            print(f"\n■ {d['status'].upper()} sau {d['steps']} bước · tổng tokens in={u.input_tokens} "
                  f"out={u.output_tokens} thinking={u.thinking_tokens}")
            if self.path:
                print(f"  Trace: {self.path}")


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
