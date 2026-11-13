"""Dựng bảng benchmark (markdown) và chèn vào README giữa <!-- BENCH:START --> … <!-- BENCH:END -->.

Bảng được SINH TỪ FILE KẾT QUẢ, không điền tay → con số trong README luôn truy ngược được về dữ liệu.

    python -m benchmarks.report                  # dùng file kết quả mới nhất
    python -m benchmarks.report results/X.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from app.bootstrap import load_pricing
from app.config import ROOT

README = ROOT / "README.md"
RESULTS_DIR = Path(__file__).with_name("results")
START, END = "<!-- BENCH:START -->", "<!-- BENCH:END -->"
SUITE_LABEL = {"finance": "Finance", "schedule": "Schedule", "mixed": "Liên miền"}


def _pct(passed: int, total: int) -> str:
    return f"{passed}/{total} ({passed / total:.0%})" if total else "—"


def _secs(ms: int | None) -> str:
    return f"{ms / 1000:.1f}s" if ms is not None else "—"


def render_table(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    suites = payload["suites"]
    pricing = load_pricing()
    head = ["Cấu hình", "Model", "Đạt", "An toàn", *[SUITE_LABEL.get(s, s) for s in suites],
            "p50", "p95", "Token vào/ca", "Token ra/ca", "Bước/ca", "Chi phí/ca"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        cost_vnd = pricing.to_vnd(r["avg_cost_usd"])
        cost = f"{cost_vnd:,}đ".replace(",", ".") if cost_vnd is not None else "—"
        label = {"single": "Single-agent", "supervisor": "Multi-agent (Supervisor)"}.get(r["agent"], r["agent"])
        cells = [label, f"`{r['model']}`", _pct(r["passed"], r["done"]), _pct(r["safety_passed"], r["safety_total"]),
                 *[_pct(r["by_suite"].get(s, {}).get("passed", 0), r["by_suite"].get(s, {}).get("done", 0))
                   for s in suites],
                 _secs(r["p50_ms"]), _secs(r["p95_ms"]), f"{r['avg_input_tokens']:,}".replace(",", "."),
                 f"{r['avg_output_tokens']:,}".replace(",", "."), str(r["avg_steps"]), cost]
        lines.append("| " + " | ".join(cells) + " |")
    notes = [f"\n_Chạy lúc {payload['ran_at']} · bộ ca: {', '.join(suites)} · sinh bởi `benchmarks/report.py`._"]
    incomplete = [r["agent"] for r in rows if r["skipped"]]
    if incomplete:
        notes.append(f"_⚠ Chưa đủ ca (hết quota) với: {', '.join(incomplete)} — chưa đủ để kết luận._")
    return "\n".join(lines + notes)


def update_readme(payload: dict[str, Any], readme: Path = README) -> None:
    text = readme.read_text(encoding="utf-8")
    if START not in text or END not in text.split(START, 1)[1]:
        raise ValueError("README thiếu cặp marker BENCH:START/BENCH:END")
    before, rest = text.split(START, 1)
    after = rest.split(END, 1)[1]
    readme.write_text(f"{before}{START}\n{render_table(payload)}\n{END}{after}", encoding="utf-8")


def latest_result() -> Path:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        sys.exit("Chưa có kết quả benchmark — chạy `python -m benchmarks.run` trước.")
    return files[-1]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_result()
    data = json.loads(path.read_text(encoding="utf-8"))
    print(render_table(data))
    update_readme(data)
