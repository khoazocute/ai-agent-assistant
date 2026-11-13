"""Dòng lệnh để dùng thử agent và xem vận hành (trước/song song với Telegram/web).

    python -m app.cli chat [--agent schedule] [--quiet]   chat với agent, in Thought/Action/Observation
    python -m app.cli summary [period]   báo cáo thu chi — gọi THẲNG service, không qua LLM
    python -m app.cli list [n]           n giao dịch gần nhất
    python -m app.cli events [days]      lịch từ hôm nay tới `days` ngày sau + việc cần làm
    python -m app.cli runs [n]           các run gần nhất (từ DB)
    python -m app.cli run <run_id>       xem lại CHÍNH XÁC prompt + tool từng bước của một run
    python -m app.cli stats              thống kê theo agent: thành công, p50/p95, token, chi phí
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import get_args

from app.db.session import session_scope


def vnd(amount: int) -> str:
    return f"{amount:,}đ".replace(",", ".")


def cmd_chat(quiet: bool) -> None:
    from app.agents.finance.agent import FinanceAgent
    from app.bootstrap import make_llm, make_tracer, setup_database

    factory = setup_database()
    agent = FinanceAgent(make_llm(), factory)
    print(f"Finance Agent · model {agent.llm.model} · prompt {agent.prompt.version}. Gõ 'thoát' để dừng.\n")
    while True:
        try:
            text = input("Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"thoát", "thoat", "exit", "quit"}:
            break
        if not text:
            continue
        tracer = make_tracer(factory, channel="cli", console=not quiet)
        try:
            result = agent.run(text, tracer)
        except Exception as e:  # lỗi mạng/API sau khi đã retry: báo và cho nhập tiếp, không thoát
            print(f"⚠ Lỗi khi gọi model: {type(e).__name__}: {e}\n")
            continue
        print(f"\nAgent: {result.answer}\n" if quiet else f"  (run {tracer.run_id})\n")


def cmd_summary(period: str) -> None:
    from app.bootstrap import setup_database
    from app.services.finance_service import FinanceService, resolve_period

    with session_scope(setup_database()) as s:
        svc = FinanceService(s)
        start, end = resolve_period(period, svc.today())  # type: ignore[arg-type]
        r = svc.get_summary(start, end)
    print(f"Thu chi {start:%d/%m/%Y} → {end:%d/%m/%Y} ({r.transaction_count} giao dịch)")
    for c in r.by_category:
        pct = f" ({c.percent_of_expense}%)" if c.percent_of_expense is not None else ""
        sign = "+" if c.kind == "income" else "-"
        print(f"  {sign} {c.category_name:<18}{vnd(c.amount_vnd):>14}{pct}")
    print(f"  Tổng chi {vnd(r.total_expense_vnd)} · Tổng thu {vnd(r.total_income_vnd)} · "
          f"Chi ròng {vnd(r.net_spending_vnd)}")


def cmd_list(limit: int) -> None:
    from app.bootstrap import setup_database
    from app.services.finance_service import FinanceService

    with session_scope(setup_database()) as s:
        rows = FinanceService(s).list_transactions(limit=limit)
    for t in rows:
        sign = "+" if t.kind == "income" else "-"
        print(f"  #{t.id:<4} {t.occurred_on:%d/%m} {sign}{vnd(t.amount_vnd):>12}  {t.category_name:<16} {t.note}")
    if not rows:
        print("  (chưa có giao dịch)")


def cmd_events(days: int) -> None:
    from datetime import timedelta

    from app.bootstrap import setup_database
    from app.config import today_vn
    from app.services.schedule_service import ScheduleService

    with session_scope(setup_database()) as s:
        svc = ScheduleService(s)
        events = svc.list_events(today_vn(), today_vn() + timedelta(days=days))
        tasks = svc.list_tasks()
    for e in events:
        print(f"  #{e.id:<4} {e.start_at:%a %d/%m %H:%M}–{e.end_at:%H:%M}  {e.title}")
    if not events:
        print("  (không có sự kiện)")
    for t in tasks:
        deadline = f" · hạn {t.deadline:%d/%m %H:%M}" if t.deadline else ""
        print(f"  việc #{t.id:<3} [{t.status}] {t.title} ({t.duration_min} phút{deadline})")


def cmd_runs(limit: int) -> None:
    from app.bootstrap import load_pricing, setup_database
    from app.harness.agentops.store import recent_runs

    pricing = load_pricing()
    runs = recent_runs(setup_database(), limit)
    for r in runs:
        cost = pricing.to_vnd(r.cost_usd)
        cost_text = vnd(cost) if cost is not None else "—"
        print(f"  {r.run_id}  {r.started_at:%d/%m %H:%M}  {r.agent:<10} {r.status:<9} {r.steps} bước "
              f"{(r.latency_ms or 0) / 1000:>5.1f}s  {r.input_tokens:>6} tok  {cost_text:>8}"
              f"  {' '.join(r.input.split())[-60:]}")
    if not runs:
        print("  (chưa có run nào — chạy `python -m app.cli chat`)")


def cmd_run(run_id: str) -> None:
    """In lại một run từ DB: đây là cách trả lời câu hỏi "agent đã đọc prompt nào, gọi tool nào?"."""
    from app.bootstrap import setup_database
    from app.harness.agentops.store import child_runs, run_events

    factory = setup_database()
    run, events = run_events(factory, run_id)
    if run is None:
        sys.exit(f"Không thấy run '{run_id}'")
    print(f"RUN {run.run_id} · {run.agent} · {run.model} · prompt {run.prompt_version} · {run.status}")
    for e in events:
        d = e.data
        if e.type == "run_start":
            print(f"\n[SYSTEM PROMPT]\n{d.get('system', '')}\n")
            print("[TOOLS] " + ", ".join(t["name"] for t in d.get("tools", [])))
            print(f"\n[USER] {d.get('input')}")
        elif e.type == "llm_response":
            print(f"\n── Bước {d['step']} · {d['latency_ms']} ms · in={d['usage']['input_tokens']}")
            for t in d["thoughts"]:
                print(f"  [THOUGHT] {' '.join(t.split())[:500]}")
            for c in d["tool_calls"]:
                print(f"  [ACTION]  {c['name']}({json.dumps(c['args'], ensure_ascii=False)})")
            if d["text"]:
                print(f"  [ANSWER]  {d['text']}")
        elif e.type == "tool_call":
            print(f"  [OBSERVATION] ({d.get('status')}) {json.dumps(d['output'], ensure_ascii=False)[:500]}")
        elif e.type == "run_end" and d.get("error"):
            print(f"\n❌ {d['error']}")
    for child in child_runs(factory, run.run_id):
        print(f"\n  ↳ run con {child.run_id} · {child.agent} · {child.status} — `python -m app.cli run {child.run_id}`")


def cmd_stats() -> None:
    from app.bootstrap import load_pricing, setup_database
    from app.harness.agentops.metrics import agent_stats

    pricing = load_pricing()
    stats = agent_stats(setup_database())
    print(f"  {'agent':<12}{'runs':>5}{'ok%':>6}{'p50':>8}{'p95':>8}"
          f"{'tok vào':>9}{'tok ra':>8}{'bước':>6}{'chi phí':>10}")
    for s in stats:
        cost = pricing.to_vnd(s.total_cost_usd)
        p50 = f"{s.p50_ms / 1000:.1f}s" if s.p50_ms is not None else "—"
        p95 = f"{s.p95_ms / 1000:.1f}s" if s.p95_ms is not None else "—"
        print(f"  {s.agent:<12}{s.runs:>5}{s.success_rate:>6.0%}{p50:>8}{p95:>8}{s.avg_input_tokens:>9}"
              f"{s.avg_output_tokens:>8}{s.avg_steps:>6}{vnd(cost) if cost is not None else '—':>10}")
    if not stats:
        print("  (chưa có dữ liệu)")


def main() -> None:
    from app.agents.registry import AGENT_NAMES
    from app.services.finance_service import Period

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="chat với agent")
    chat.add_argument("--agent", default="finance", choices=AGENT_NAMES)
    chat.add_argument("--quiet", action="store_true", help="chỉ in câu trả lời, không in trace")
    summary = sub.add_parser("summary", help="báo cáo thu chi (không qua LLM)")
    summary.add_argument("period", nargs="?", default="this_month", choices=get_args(Period))
    sub.add_parser("list", help="giao dịch gần nhất").add_argument("limit", nargs="?", type=int, default=20)
    sub.add_parser("events", help="lịch sắp tới").add_argument("days", nargs="?", type=int, default=7)
    sub.add_parser("runs", help="các run gần nhất").add_argument("limit", nargs="?", type=int, default=20)
    sub.add_parser("run", help="xem chi tiết một run").add_argument("run_id")
    sub.add_parser("stats", help="thống kê vận hành theo agent")

    args = parser.parse_args()
    match args.command:
        case "chat":
            cmd_chat(args.agent, args.quiet)
        case "summary":
            cmd_summary(args.period)
        case "list":
            cmd_list(args.limit)
        case "events":
            cmd_events(args.days)
        case "runs":
            cmd_runs(args.limit)
        case "run":
            cmd_run(args.run_id)
        case "stats":
            cmd_stats()


if __name__ == "__main__":
    main()
