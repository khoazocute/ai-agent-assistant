"""Bản tin = WORKFLOW cố định, không phải agent (ADR-0014).

    code gom dữ liệu (BriefingService) → 1 lần gọi LLM viết lời (không tool) → gửi
                                       └─ LLM lỗi / hết quota → mẫu dựng sẵn (fallback_text)

Vì sao không dùng agent ReAct: các bước đã biết trước, không cần model tự quyết gọi tool nào. Workflow
rẻ hơn (1 lượt gọi), nhanh hơn, dễ đoán hơn — và số liệu không thể sai vì không do model tính.
Vẫn dùng run_react (với 0 tool) để có trace/chi phí như mọi run khác.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.harness.agentops.tracer import Tracer
from app.harness.context.prompts import load_prompt
from app.harness.orchestration.llm_client import LLMClient
from app.harness.orchestration.react_loop import run_react
from app.harness.tools.executor import ToolExecutor
from app.harness.tools.registry import ToolRegistry
from app.services.briefing_service import BriefData, fallback_text

PROMPT_PATH = Path(__file__).with_name("prompt.md")


def compose_brief(llm: LLMClient | None, data: BriefData, tracer: Tracer | None = None) -> tuple[str, str]:
    """Trả về (nội dung, nguồn) với nguồn = "llm" | "fallback"."""
    if llm is None:
        return fallback_text(data), "fallback"
    prompt = load_prompt(PROMPT_PATH)
    message = (f"Viết {'bản tin sáng' if data.kind == 'morning' else 'tổng kết tối'} từ dữ liệu sau:\n"
               f"```json\n{json.dumps(data.model_dump(mode='json'), ensure_ascii=False, indent=1)}\n```")
    try:
        result = run_react(llm, prompt.text, message, ToolExecutor(ToolRegistry()), max_steps=1, tracer=tracer,
                           meta={"agent": "briefing", "prompt_version": prompt.version, "channel": "job"})
    except Exception:
        return fallback_text(data), "fallback"
    if result.status != "ok" or not result.answer.strip():
        return fallback_text(data), "fallback"
    return result.answer.strip(), "llm"
