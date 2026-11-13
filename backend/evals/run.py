"""Chạy eval cho agent với LLM thật.

    cd backend
    python -m evals.run                          # chạy tất cả ca finance
    python -m evals.run --case fin-001 --case fin-013   # chỉ vài ca (lọc theo tiền tố id)
    python -m evals.run --limit 5 --delay 5      # 5 ca đầu, nghỉ 5s giữa các ca (tránh giới hạn/phút)
    python -m evals.run --model gemini-3.5-flash-lite

Mỗi ca chạy trên một DB SQLite MỚI trong RAM với "bây giờ" cố định → các ca độc lập, lặp lại được.
Hết quota (429) → dừng, các ca còn lại đánh dấu "chưa chạy", vẫn lưu kết quả đã có.
Kết quả: backend/data/evals/<agent>-<thời điểm>.json · trace từng ca: backend/data/traces/evals/
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from app.agents.finance.agent import FinanceAgent
from app.bootstrap import setup_database
from app.config import ROOT, VN_TZ, get_settings
from app.db.session import session_scope
from app.harness.agentops.tracer import Tracer
from app.harness.evaluation.scorer import CaseResult, Check, EvalSummary, check_answer, check_tools, format_report
from app.harness.orchestration.llm_client import LLMClient
from app.services.finance_service import FinanceService, TransactionOut

CASES_DIR = Path(__file__).with_name("cases")
RESULTS_DIR = ROOT / "backend" / "data" / "evals"
TRACE_DIR = ROOT / "backend" / "data" / "traces" / "evals"
NOW = datetime(2026, 11, 13, 12, 30, tzinfo=VN_TZ)  # Thứ Sáu — khớp chú thích trong cases/*.yaml


# ---------- Định dạng ca (extra="forbid": gõ sai tên khoá trong YAML → báo lỗi ngay) ----------

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetupTx(_Strict):
    amount_vnd: int
    category: str
    occurred_on: date
    note: str = ""


class ExpectedTx(_Strict):
    amount_vnd: int
    category: str | list[str]
    occurred_on: date | str  # date, "today" hoặc "yesterday"

    def matches(self, t: TransactionOut) -> bool:
        categories = [self.category] if isinstance(self.category, str) else self.category
        return t.amount_vnd == self.amount_vnd and t.category in categories and t.occurred_on == self.day()

    def day(self) -> date:
        if self.occurred_on == "today":
            return NOW.date()
        if self.occurred_on == "yesterday":
            return NOW.date() - timedelta(days=1)
        return self.occurred_on if isinstance(self.occurred_on, date) else date.fromisoformat(self.occurred_on)

    def label(self) -> str:
        return f"{self.amount_vnd}/{self.category}/{self.day()}"


class Expect(_Strict):
    transactions: list[ExpectedTx] = []
    must_call: list[str] = []
    must_not_call: list[str] = []
    answer_numbers: list[int] = []
    answer_not_contains: list[str] = []
    asks_clarification: bool = False


class EvalCase(_Strict):
    id: str
    input: str
    safety: bool = False
    setup: list[SetupTx] = []
    expect: Expect = Expect()


class QuotaExhausted(Exception):
    pass


def load_cases(agent: str) -> list[EvalCase]:
    raw = yaml.safe_load((CASES_DIR / f"{agent}.yaml").read_text(encoding="utf-8"))
    cases = [EvalCase.model_validate(item) for item in raw]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Trùng id ca eval")
    return cases


# ---------- Chạy & chấm một ca ----------

def run_case(case: EvalCase, llm: LLMClient, trace_dir: Path | None = None) -> CaseResult:
    factory = setup_database("sqlite://")  # DB mới tinh cho mỗi ca
    with session_scope(factory) as s:
        svc = FinanceService(s, today=lambda: NOW.date())
        setup_ids = {svc.add_transaction(t.amount_vnd, t.category, t.occurred_on, t.note).id for t in case.setup}

    result = CaseResult(case.id, case.safety)
    tracer = Tracer(directory=trace_dir)
    result.trace_path = str(tracer.path or "")
    start = time.perf_counter()
    try:
        run = FinanceAgent(llm, factory, now=lambda: NOW).run(case.input, tracer)
    except Exception as e:
        if getattr(e, "code", None) == 429:
            raise QuotaExhausted(str(e)) from e
        result.status, result.error = "error", f"{type(e).__name__}: {e}"
        return result
    result.latency_ms = round((time.perf_counter() - start) * 1000)
    result.answer, result.steps = run.answer, run.steps
    result.tool_calls = [c.name for c in run.tool_calls]
    result.input_tokens, result.output_tokens = run.usage.input_tokens, run.usage.output_tokens

    with session_scope(factory) as s:
        after = FinanceService(s).list_transactions(limit=1000)
    new_rows = [t for t in after if t.id not in setup_ids]
    remaining_ids = {t.id for t in after}

    e = case.expect
    result.checks = [
        Check("run_ok", run.status == "ok", run.status),
        _check_new_rows(e.transactions, new_rows),
        # Áp dụng cho MỌI ca: không có gì bị xoá khi chưa duyệt.
        Check("setup_intact", setup_ids <= remaining_ids, f"mất id: {sorted(setup_ids - remaining_ids)}"),
        *check_tools(result.tool_calls, e.must_call, e.must_not_call),
        *check_answer(run.answer, e.answer_numbers, e.answer_not_contains, e.asks_clarification),
    ]
    return result


def _check_new_rows(expected: list[ExpectedTx], actual: list[TransactionOut]) -> Check:
    """Khớp đúng từng dòng: thiếu một khoản hay ghi thừa một khoản đều trượt."""
    unmatched = list(actual)
    missing = []
    for exp in expected:
        hit = next((t for t in unmatched if exp.matches(t)), None)
        if hit:
            unmatched.remove(hit)
        else:
            missing.append(exp.label())
    extra = [f"{t.amount_vnd}/{t.category}/{t.occurred_on}" for t in unmatched]
    return Check("db_transactions", not missing and not extra, f"thiếu: {missing} · thừa: {extra}")


# ---------- CLI ----------

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m evals.run")
    parser.add_argument("--agent", default="finance", choices=["finance"])
    parser.add_argument("--case", action="append", default=[], help="lọc theo tiền tố id (lặp được)")
    parser.add_argument("--limit", type=int, help="chỉ chạy N ca đầu")
    parser.add_argument("--model", help="ghi đè GEMINI_MODEL")
    parser.add_argument("--delay", type=float, default=0, help="giây nghỉ giữa các ca")
    args = parser.parse_args()

    from app.harness.orchestration.llm_client import GeminiClient

    settings = get_settings()
    llm = GeminiClient(api_key=settings.gemini_api_key, model=args.model or settings.gemini_model)
    cases = [c for c in load_cases(args.agent) if not args.case or any(c.id.startswith(p) for p in args.case)]
    cases = cases[: args.limit] if args.limit else cases

    results: list[CaseResult] = []
    quota_hit = False
    for i, case in enumerate(cases, 1):
        if quota_hit:
            results.append(CaseResult(case.id, case.safety, status="skipped"))
            continue
        print(f"[{i}/{len(cases)}] {case.id} …", flush=True)
        try:
            results.append(run_case(case, llm, TRACE_DIR))
        except QuotaExhausted:
            print("  ⛔ Hết quota (429) — dừng, các ca còn lại để lần sau.")
            quota_hit = True
            results.append(CaseResult(case.id, case.safety, status="skipped"))
        if args.delay and i < len(cases) and not quota_hit:
            time.sleep(args.delay)

    prompt_version = FinanceAgent(llm, setup_database("sqlite://")).prompt.version
    meta = {"agent": args.agent, "model": llm.model, "prompt_version": prompt_version,
            "subset": bool(args.case or args.limit), "ran_at": datetime.now(VN_TZ).isoformat(timespec="seconds")}
    print("\n" + format_report(results, meta))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{args.agent}-{datetime.now(VN_TZ):%Y%m%d-%H%M%S}.json"
    summary = EvalSummary.of(results)
    payload = {"meta": meta, "summary": {**dataclasses.asdict(summary), "pass_rate": summary.pass_rate,
                                         "safety_rate": summary.safety_rate,
                                         "meets_threshold": summary.meets_threshold and not meta["subset"]},
               "results": [dataclasses.asdict(r) | {"passed": r.passed} for r in results]}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKết quả: {out}")


if __name__ == "__main__":
    main()
