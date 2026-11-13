"""Nạp system prompt từ file `prompt.md` của agent.

Prompt nằm trong file .md riêng (không phải chuỗi trong code) để: đọc/sửa như tài liệu, diff rõ ràng
trong git, và có version = hash nội dung → mỗi trace ghi được "run này dùng prompt phiên bản nào".
Bước 6 mở rộng thành PromptRegistry (lưu DB, chỉ kích hoạt khi eval đạt ngưỡng).

Định dạng:
    ---
    agent: finance
    description: ...
    ---
    <nội dung system prompt>
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Prompt:
    text: str  # phần model đọc (không gồm frontmatter)
    version: str  # 8 ký tự đầu của sha256(text) — đổi 1 chữ là đổi version
    meta: dict[str, str] = field(default_factory=dict)


def load_prompt(path: Path) -> Prompt:
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---\n"):
        header, sep, rest = raw[4:].partition("\n---\n")
        if not sep:
            raise ValueError(f"{path}: frontmatter mở bằng '---' nhưng không có dòng '---' đóng.")
        for line in header.splitlines():
            if line.strip():
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
        body = rest
    text = body.strip()
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return Prompt(text=text, version=version, meta=meta)
