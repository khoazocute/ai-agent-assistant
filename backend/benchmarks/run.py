"""Benchmark single-agent vs multi-agent (Supervisor) trên CÙNG bộ ca eval.

    cd backend
    python -m benchmarks.run --delay 5                         # single + supervisor, cả 3 bộ ca
    python -m benchmarks.run --agents single --suite mixed     # một phần
    python -m benchmarks.report                                # dựng lại bảng README từ kết quả mới nhất

Đo: tỉ lệ đạt (tổng, an toàn, từng bộ), độ trễ p50/p95, token vào/ra trung bình, chi phí/ca.
Kết quả tóm tắt: benchmarks/results/<thời điểm>.json (commit được — là bằng chứng cho ADR-0008);
chi tiết từng ca: backend/data/evals/ (không commit).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.bootstrap import load_pricing, make_llm
from app.config import VN_TZ
from app.harness.agentops.metrics import percentile
from app.harness.evaluation.scorer import CaseResult, EvalSummary
from evals.run import ALL_SUITES, cases_for, run_cases, save_results

RESULTS_DIR = Path(__file__).with_name("results")


def summarize(agent: str, model: str, results: list[CaseResult], suite_of: dict[str, str]) -> dict[str, Any]:
    s = EvalSummary.of(results)
    done = [r for r in results if r.status != "skipped"]
    latencies = [r.latency_ms for r in done if r.status == "done"]
    pricing = load_pricing()
    costs = [pricing.cost_usd(model, r.input_tokens, r.output_tokens) for r in done]
    by_suite = {}
    for suite in sorted({suite_of[r.case_id] for r in results}):
        rs = [r for r in done if suite_of[r.case_id] == suite]
        by_suite[suite] = {"passed": sum(r.passed for r in rs), "done": len(rs)}
    return {
        "agent": agent, "model": model, "cases": s.total, "done": s.done, "skipped": s.skipped,
        "passed": s.passed, "pass_rate": s.pass_rate,
        "safety_passed": s.safety_passed, "safety_total": s.safety_total, "safety_rate": s.safety_rate,
        "errors": sum(r.status == "error" for r in results), "by_suite": by_suite,
        "p50_ms": percentile(latencies, 50), "p95_ms": percentile(latencies, 95),
        "avg_input_tokens": round(sum(r.input_tokens for r in done) / len(done)) if done else 0,
        "avg_output_tokens": round(sum(r.output_tokens for r in done) / len(done)) if done else 0,
        "avg_steps": round(sum(r.steps for r in done) / len(done), 1) if done else 0,
        "avg_cost_usd": (sum(costs) / len(costs)) if costs and None not in costs else None,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m benchmarks.run")
    parser.add_argument("--agents", nargs="+", default=["single", "supervisor"])
    parser.add_argument("--suite", action="append", choices=ALL_SUITES)
    parser.add_argument("--model")
    parser.add_argument("--delay", type=float, default=0)
    args = parser.parse_args()

    llm = make_llm(args.model)
    suites = args.suite or ALL_SUITES
    rows = []
    for agent in args.agents:
        cases = cases_for(agent, suites)
        suite_of = {c.id: c.suite for c in cases}
        results = run_cases(cases, llm, agent, args.delay)
        save_results(results, {"agent": agent, "model": llm.model, "suites": suites, "benchmark": True,
                               "ran_at": datetime.now(VN_TZ).isoformat(timespec="seconds")})
        rows.append(summarize(agent, llm.model, results, suite_of))
        if results and results[-1].status == "skipped":
            print("⛔ Hết quota — dừng benchmark, lưu phần đã có.")
            break

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{datetime.now(VN_TZ):%Y%m%d-%H%M%S}.json"
    payload = {"ran_at": datetime.now(VN_TZ).isoformat(timespec="seconds"), "suites": suites, "rows": rows}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    from benchmarks.report import render_table, update_readme

    print("\n" + render_table(payload))
    update_readme(payload)
    print(f"\nĐã lưu {out} và cập nhật bảng trong README.md")


if __name__ == "__main__":
    main()
