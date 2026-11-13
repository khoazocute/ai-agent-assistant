"""Chạy eval cho agent với LLM thật.

    cd backend
    python -m evals.run --agent finance                    # bộ ca finance
    python -m evals.run --agent schedule                   # bộ ca schedule
    python -m evals.run --agent single                     # finance + schedule + mixed (liên miền)
    python -m evals.run --agent single --suite mixed       # chỉ một bộ
    python -m evals.run --case fin-001 --case sch-003      # vài ca (lọc theo tiền tố id)
    python -m evals.run --limit 5 --delay 5 --model gemini-3.5-flash-lite

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
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from app.agents.registry import AGENT_NAMES, build_agent
from app.bootstrap import setup_database
from app.config import DATA_DIR, VN_TZ, get_settings
from app.db.session import session_scope
from app.harness.agentops.tracer import Tracer
from app.harness.evaluation.scorer import CaseResult, Check, EvalSummary, check_answer, check_tools, format_report
from app.harness.orchestration.llm_client import LLMClient
from app.services.finance_service import FinanceService, TransactionOut
from app.services.schedule_service import EventOut, ScheduleService, TaskOut

CASES_DIR = Path(__file__).with_name("cases")
RESULTS_DIR = DATA_DIR / "evals"
TRACE_DIR = DATA_DIR / "traces" / "evals"
NOW = datetime(2026, 11, 13, 12, 30, tzinfo=VN_TZ)  # Thứ Sáu — khớp chú thích trong cases/*.yaml
NOW_LOCAL = NOW.replace(tzinfo=None)

# Agent nào chạy bộ ca nào. Single/supervisor chạy CÙNG bộ ca → so sánh công bằng (benchmark bước 9).
SUITES_FOR_AGENT = {"finance": ["finance"], "schedule": ["schedule"]}
ALL_SUITES = ["finance", "schedule", "mixed"]


# ---------- Định dạng ca (extra="forbid": gõ sai tên khoá trong YAML → báo lỗi ngay) ----------

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _day(value: date | str) -> date:
    if value == "today":
        return NOW.date()
    if value == "yesterday":
        return NOW.date() - timedelta(days=1)
    if value == "tomorrow":
        return NOW.date() + timedelta(days=1)
    return value if isinstance(value, date) else date.fromisoformat(value)


def _any_in(needles: str | list[str], haystack: str) -> bool:
    options = [needles] if isinstance(needles, str) else needles
    return any(n.lower() in haystack.lower() for n in options)


class SetupTx(_Strict):
    amount_vnd: int
    category: str
    occurred_on: date
    note: str = ""


class SetupEvent(_Strict):
    title: str
    start: datetime
    end: datetime


class SetupTask(_Strict):
    title: str
    duration_min: int
    deadline: datetime | None = None
    priority: int = 2


class Setup(_Strict):
    transactions: list[SetupTx] = []
    events: list[SetupEvent] = []
    tasks: list[SetupTask] = []


class ExpectedTx(_Strict):
    amount_vnd: int
    category: str | list[str]
    occurred_on: date | str  # date | today | yesterday

    def matches(self, t: TransactionOut) -> bool:
        categories = [self.category] if isinstance(self.category, str) else self.category
        return t.amount_vnd == self.amount_vnd and t.category in categories and t.occurred_on == _day(self.occurred_on)

    def label(self) -> str:
        return f"{self.amount_vnd}/{self.category}/{_day(self.occurred_on)}"


class ExpectedEvent(_Strict):
    title_contains: str | list[str]
    start: datetime
    end: datetime | None = None  # bỏ trống = không kiểm tra giờ kết thúc

    def matches(self, e: EventOut) -> bool:
        return _any_in(self.title_contains, e.title) and e.start_at == self.start and (
            self.end is None or e.end_at == self.end)

    def label(self) -> str:
        return f"{self.title_contains}@{self.start:%d/%m %H:%M}"


class ExpectedTask(_Strict):
    title_contains: str | list[str]
    duration_min: int

    def matches(self, t: TaskOut) -> bool:
        return _any_in(self.title_contains, t.title) and t.duration_min == self.duration_min

    def label(self) -> str:
        return f"{self.title_contains}/{self.duration_min}p"


class Expect(_Strict):
    transactions: list[ExpectedTx] = []  # giao dịch MỚI — khớp chính xác
    events: list[ExpectedEvent] = []  # sự kiện MỚI — khớp chính xác
    events_final: list[ExpectedEvent] | None = None  # TOÀN BỘ sự kiện sau khi chạy (cho ca sửa/dời)
    tasks: list[ExpectedTask] = []  # việc MỚI — khớp chính xác
    must_call: list[str] = []
    must_not_call: list[str] = []
    answer_numbers: list[int] = []
    answer_contains: list[str | list[str]] = []
    answer_not_contains: list[str] = []
    asks_clarification: bool = False


class EvalCase(_Strict):
    id: str
    input: str
    safety: bool = False
    setup: Setup = Setup()
    expect: Expect = Expect()
    suite: str = ""


class QuotaExhausted(Exception):
    pass


def load_cases(suite: str) -> list[EvalCase]:
    raw = yaml.safe_load((CASES_DIR / f"{suite}.yaml").read_text(encoding="utf-8"))
    cases = [EvalCase.model_validate({**item, "suite": suite}) for item in raw]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Trùng id ca eval trong {suite}.yaml")
    return cases


def cases_for(agent: str, suites: list[str] | None = None) -> list[EvalCase]:
    chosen = suites or SUITES_FOR_AGENT.get(agent, ALL_SUITES)
    return [c for s in chosen for c in load_cases(s)]


# ---------- Chạy & chấm một ca ----------

@dataclasses.dataclass
class World:
    transactions: list[TransactionOut]
    events: list[EventOut]
    tasks: list[TaskOut]


def snapshot(factory) -> World:
    with session_scope(factory) as s:
        sched = ScheduleService(s, now=lambda: NOW)
        return World(FinanceService(s).list_transactions(limit=1000),
                     sched.list_events(date(2000, 1, 1), date(2100, 1, 1)), sched.list_tasks())


def run_case(case: EvalCase, llm: LLMClient, agent: str = "finance", trace_dir: Path | None = None) -> CaseResult:
    factory = setup_database("sqlite://")  # DB mới tinh cho mỗi ca
    with session_scope(factory) as s:
        fin, sched = FinanceService(s, today=lambda: NOW.date()), ScheduleService(s, now=lambda: NOW)
        for t in case.setup.transactions:
            fin.add_transaction(t.amount_vnd, t.category, t.occurred_on, t.note)
        for e in case.setup.events:
            sched.create_event(e.title, e.start, e.end)
        for t in case.setup.tasks:
            sched.add_task(t.title, t.duration_min, t.deadline, t.priority)
    before = snapshot(factory)

    result = CaseResult(case.id, case.safety)
    tracer = Tracer(directory=trace_dir)
    result.trace_path = str(tracer.path or "")
    start = time.perf_counter()
    try:
        run = build_agent(agent, llm, factory, now=lambda: NOW).run(case.input, tracer, meta={"channel": "eval"})
    except Exception as e:
        if getattr(e, "code", None) == 429:
            raise QuotaExhausted(str(e)) from e
        result.status, result.error = "error", f"{type(e).__name__}: {e}"
        return result
    result.latency_ms = round((time.perf_counter() - start) * 1000)
    result.answer, result.steps = run.answer, run.steps
    result.tool_calls = [c.name for c in run.tool_calls]
    result.input_tokens = run.usage.input_tokens
    result.output_tokens = run.usage.output_tokens + run.usage.thinking_tokens  # thinking tính như token ra

    after = snapshot(factory)
    e = case.expect
    new_tx = [t for t in after.transactions if t.id not in {b.id for b in before.transactions}]
    new_events = [x for x in after.events if x.id not in {b.id for b in before.events}]
    new_tasks = [t for t in after.tasks if t.id not in {b.id for b in before.tasks}]
    checks = [
        Check("run_ok", run.status == "ok", run.status),
        _match("db_transactions", e.transactions, new_tx, lambda t: f"{t.amount_vnd}/{t.category}/{t.occurred_on}"),
        _match("db_events", e.events, new_events, lambda x: f"{x.title}@{x.start_at:%d/%m %H:%M}"),
        _match("db_tasks", e.tasks, new_tasks, lambda t: f"{t.title}/{t.duration_min}p"),
        # Áp dụng cho MỌI ca: không có gì bị xoá khi chưa duyệt.
        Check("setup_intact", {t.id for t in before.transactions} <= {t.id for t in after.transactions}
              and {x.id for x in before.events} <= {x.id for x in after.events}, "dữ liệu có sẵn bị mất"),
        *check_tools(result.tool_calls, e.must_call, e.must_not_call),
        *check_answer(run.answer, e.answer_numbers, e.answer_not_contains, e.asks_clarification),
        *[Check(f"answer_contains:{c}", _any_in(c, run.answer)) for c in e.answer_contains],
    ]
    if e.events_final is not None:
        checks.append(_match("db_events_final", e.events_final, after.events,
                             lambda x: f"{x.title}@{x.start_at:%d/%m %H:%M}"))
    result.checks = checks
    return result


def _match(name: str, expected: list[Any], actual: list[Any], show) -> Check:
    """Khớp đúng từng dòng: thiếu một mục hay thừa một mục đều trượt."""
    unmatched = list(actual)
    missing = []
    for exp in expected:
        hit = next((a for a in unmatched if exp.matches(a)), None)
        if hit:
            unmatched.remove(hit)
        else:
            missing.append(exp.label())
    return Check(name, not missing and not unmatched, f"thiếu: {missing} · thừa: {[show(a) for a in unmatched]}")


# ---------- Chạy nhiều ca (dùng chung cho benchmark) ----------

def run_cases(cases: list[EvalCase], llm: LLMClient, agent: str, delay: float = 0,
              progress: bool = True) -> list[CaseResult]:
    results: list[CaseResult] = []
    quota_hit = False
    for i, case in enumerate(cases, 1):
        if quota_hit:
            results.append(CaseResult(case.id, case.safety, status="skipped"))
            continue
        if progress:
            print(f"[{i}/{len(cases)}] {agent} · {case.id} …", flush=True)
        try:
            results.append(run_case(case, llm, agent, TRACE_DIR))
        except QuotaExhausted:
            print("  ⛔ Hết quota (429) — dừng, các ca còn lại để lần sau.")
            quota_hit = True
            results.append(CaseResult(case.id, case.safety, status="skipped"))
        if delay and i < len(cases) and not quota_hit:
            time.sleep(delay)
    return results


def save_results(results: list[CaseResult], meta: dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{meta['agent']}-{datetime.now(VN_TZ):%Y%m%d-%H%M%S}.json"
    summary = EvalSummary.of(results)
    payload = {"meta": meta, "summary": {**dataclasses.asdict(summary), "pass_rate": summary.pass_rate,
                                         "safety_rate": summary.safety_rate,
                                         "meets_threshold": summary.meets_threshold and not meta.get("subset")},
               "results": [dataclasses.asdict(r) | {"passed": r.passed} for r in results]}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m evals.run")
    parser.add_argument("--agent", default="finance", choices=AGENT_NAMES)
    parser.add_argument("--suite", action="append", choices=ALL_SUITES, help="bộ ca (mặc định theo agent)")
    parser.add_argument("--case", action="append", default=[], help="lọc theo tiền tố id (lặp được)")
    parser.add_argument("--limit", type=int, help="chỉ chạy N ca đầu")
    parser.add_argument("--model", help="ghi đè GEMINI_MODEL")
    parser.add_argument("--delay", type=float, default=0, help="giây nghỉ giữa các ca")
    args = parser.parse_args()

    from app.bootstrap import make_llm

    llm = make_llm(args.model)
    cases = [c for c in cases_for(args.agent, args.suite)
             if not args.case or any(c.id.startswith(p) for p in args.case)]
    cases = cases[: args.limit] if args.limit else cases
    results = run_cases(cases, llm, args.agent, args.delay)

    agent = build_agent(args.agent, llm, setup_database("sqlite://"))
    meta = {"agent": args.agent, "model": llm.model, "prompt_version": agent.prompt.version,
            "suites": args.suite or SUITES_FOR_AGENT.get(args.agent, ALL_SUITES),
            "subset": bool(args.case or args.limit), "ran_at": datetime.now(VN_TZ).isoformat(timespec="seconds"),
            "model_settings": get_settings().gemini_model}
    print("\n" + format_report(results, meta))
    print(f"\nKết quả: {save_results(results, meta)}")


if __name__ == "__main__":
    main()
