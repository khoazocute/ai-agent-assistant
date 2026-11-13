"""Ảnh hóa đơn → đề xuất giao dịch (workflow, ADR-0014).

    ảnh ─▶ 1 lượt LLM vision, KHÔNG tool, đầu ra ép theo JSON schema ─▶ code kiểm tra lại từng trường
        ─▶ PendingAction("add_transaction", …) ─▶ người dùng bấm ✅ Ghi / ❌ Bỏ ─▶ code ghi đúng số đã xem

Phòng thủ: chữ trong ảnh không tin cậy (có thể chứa "bỏ qua hướng dẫn…"). Model không có tool nào và chỉ
điền được các trường định sẵn → tệ nhất là đọc sai số; người dùng nhìn thấy số trước khi ghi.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from app.harness.agentops.tracer import Tracer
from app.harness.context.prompts import load_prompt
from app.harness.orchestration.llm_client import StructuredLLM
from app.services.finance_service import DEFAULT_CATEGORIES, CategoryKey

PROMPT_PATH = Path(__file__).with_name("prompt.md")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic"}
EXPENSE_CATEGORIES = [c for c in get_args(CategoryKey) if DEFAULT_CATEGORIES[c][1] == "expense"]

RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "readable": {"type": "boolean"},
        "merchant": {"type": "string", "description": "Tên cửa hàng/đơn vị"},
        "date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
        "total_vnd": {"type": "integer"},
        "category": {"type": "string", "enum": EXPENSE_CATEGORIES},
        "items": {"type": "array", "maxItems": 10, "items": {
            "type": "object", "properties": {"name": {"type": "string"}, "amount_vnd": {"type": "integer"}},
            "required": ["name", "amount_vnd"]}},
    },
    "required": ["readable", "total_vnd", "category"],
}


class ReceiptError(ValueError):
    pass


class ReceiptProposal(BaseModel):
    readable: bool
    merchant: str
    occurred_on: date
    total_vnd: int
    category: str
    items: list[dict]
    warnings: list[str]

    def transaction_args(self) -> dict:
        note = f"{self.merchant} (hóa đơn)" if self.merchant else "Hóa đơn"
        return {"amount_vnd": self.total_vnd, "category": self.category,
                "occurred_on": self.occurred_on.isoformat(), "note": note[:200]}

    def summary(self) -> str:
        amount = f"{self.total_vnd:,}đ".replace(",", ".")
        name = DEFAULT_CATEGORIES.get(self.category, (self.category,))[0]
        lines = [f"Ghi khoản chi {amount} · {name} · {self.occurred_on:%d/%m/%Y}" +
                 (f" · {self.merchant}" if self.merchant else "")]
        lines += [f"  - {i['name']}: {i['amount_vnd']:,}đ".replace(",", ".") for i in self.items[:5]]
        lines += [f"⚠ {w}" for w in self.warnings]
        return "\n".join(lines)


def read_receipt(llm: StructuredLLM, image: bytes, mime_type: str, today: date,
                 tracer: Tracer | None = None) -> ReceiptProposal:
    if mime_type not in ALLOWED_MIME:
        raise ReceiptError(f"Định dạng ảnh không hỗ trợ: {mime_type}. Dùng JPG/PNG/WEBP/HEIC.")
    if len(image) > MAX_IMAGE_BYTES:
        raise ReceiptError("Ảnh lớn hơn 5 MB — chụp lại hoặc nén ảnh nhỏ hơn.")
    prompt = load_prompt(PROMPT_PATH)
    tracer = tracer or Tracer()
    tracer.event("run_start", agent="receipt", prompt_version=prompt.version, model=llm.model, system=prompt.text,
                 tools=[], input=f"[ảnh {mime_type}, {len(image) // 1024} KB]")
    try:
        data, resp = llm.generate_json(prompt.text, f"Hôm nay là {today.isoformat()}. Đọc hóa đơn trong ảnh.",
                                       RECEIPT_SCHEMA, image, mime_type)
    except Exception as e:
        tracer.event("run_end", status="error", error=f"{type(e).__name__}: {e}", steps=1,
                     usage={"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0})
        raise
    tracer.event("llm_response", step=1, thoughts=resp.thoughts, text=str(data), tool_calls=[], usage=resp.usage,
                 finish_reason=resp.finish_reason, latency_ms=resp.latency_ms)
    proposal = _validate(data, today)
    tracer.event("run_end", status="ok", answer=proposal.summary(), steps=1, usage=resp.usage)
    return proposal


def _validate(data: dict, today: date) -> ReceiptProposal:
    """Không tin output của model: kiểm tra lại từng trường bằng code."""
    warnings = []
    total = data.get("total_vnd") or 0
    readable = bool(data.get("readable")) and isinstance(total, int) and total > 0
    category = data.get("category") if data.get("category") in EXPENSE_CATEGORIES else "khac"
    if category != data.get("category"):
        warnings.append("Không rõ danh mục — tạm xếp vào 'Khác'.")
    occurred = today
    try:
        parsed = date.fromisoformat(data["date"]) if data.get("date") else None
        if parsed and parsed > today:
            warnings.append(f"Ngày trên hóa đơn ({parsed:%d/%m/%Y}) ở tương lai — dùng hôm nay.")
        elif parsed:
            occurred = parsed
    except ValueError:
        warnings.append("Không đọc được ngày — dùng hôm nay.")
    items = [i for i in (data.get("items") or []) if isinstance(i, dict) and isinstance(i.get("amount_vnd"), int)]
    item_sum = sum(i["amount_vnd"] for i in items)
    if readable and items and abs(item_sum - total) > max(1000, total * 0.2):
        warnings.append(f"Tổng các món ({item_sum:,}đ) lệch nhiều so với tổng tiền — kiểm tra lại.".replace(",", "."))
    return ReceiptProposal(readable=readable, merchant=str(data.get("merchant") or "")[:100], occurred_on=occurred,
                           total_vnd=total if readable else 0, category=category, items=items, warnings=warnings)
