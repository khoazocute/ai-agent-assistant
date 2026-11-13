"""Tính chi phí một run từ số token và bảng giá (config/pricing.yaml).

Giá KHÔNG viết cứng trong code: giá thay đổi theo thời gian và theo model; cập nhật file YAML là đủ.
Model chưa có giá → chi phí = None (hiển thị "—"), không đoán bừa một con số.
Token suy nghĩ (thinking) được tính tiền như token đầu ra — đúng với cách tính của Gemini/Claude.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m_usd: float
    output_per_1m_usd: float


@dataclass
class Pricing:
    models: dict[str, ModelPrice] = field(default_factory=dict)
    usd_to_vnd: float | None = None

    @classmethod
    def load(cls, path: Path) -> Pricing:
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        models = {
            name: ModelPrice(float(p["input_per_1m_usd"]), float(p["output_per_1m_usd"]))
            for name, p in (raw.get("models") or {}).items()
            if p and p.get("input_per_1m_usd") is not None and p.get("output_per_1m_usd") is not None
        }
        return cls(models, raw.get("usd_to_vnd"))

    def cost_usd(self, model: str, input_tokens: int, output_tokens: int, thinking_tokens: int = 0) -> float | None:
        price = self.models.get(model)
        if price is None:
            return None
        return (input_tokens * price.input_per_1m_usd
                + (output_tokens + thinking_tokens) * price.output_per_1m_usd) / 1_000_000

    def to_vnd(self, usd: float | None) -> int | None:
        if usd is None or not self.usd_to_vnd:
            return None
        return round(usd * self.usd_to_vnd)
