"""Dòng lệnh để dùng thử agent trước khi có Telegram/web.

    python -m app.cli chat              # chat với Finance Agent, in Thought/Action/Observation
    python -m app.cli chat --quiet      # chỉ in câu trả lời
    python -m app.cli summary [period]  # báo cáo thu chi — gọi THẲNG service, không qua LLM
    python -m app.cli list [n]          # n giao dịch gần nhất

Lưu ý: mỗi tin nhắn là một run độc lập — agent CHƯA nhớ câu trước (memory hội thoại có ở bước 12).
"""

from __future__ import annotations

import argparse
import sys
from typing import get_args

from app.config import ROOT, get_settings
from app.db.session import session_scope

TRACE_DIR = ROOT / "backend" / "data" / "traces"


def vnd(amount: int) -> str:
    return f"{amount:,}đ".replace(",", ".")


def cmd_chat(quiet: bool) -> None:
    from app.agents.finance.agent import FinanceAgent
    from app.bootstrap import setup_database
    from app.harness.agentops.tracer import Tracer
    from app.harness.orchestration.llm_client import GeminiClient

    settings = get_settings()
    if not settings.gemini_api_key:
        sys.exit("Thiếu GEMINI_API_KEY trong .env")
    agent = FinanceAgent(GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model),
                         setup_database())
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
        try:
            result = agent.run(text, Tracer(directory=TRACE_DIR, console=not quiet))
        except Exception as e:  # lỗi mạng/API sau khi đã retry: báo và cho nhập tiếp, không thoát
            print(f"⚠ Lỗi khi gọi model: {type(e).__name__}: {e}\n")
            continue
        print(f"\nAgent: {result.answer}\n" if quiet else "")


def cmd_summary(period: str) -> None:
    from app.bootstrap import setup_database
    from app.services.finance_service import FinanceService, resolve_period

    factory = setup_database()
    with session_scope(factory) as s:
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


def main() -> None:
    from app.services.finance_service import Period

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="chat với Finance Agent")
    chat.add_argument("--quiet", action="store_true", help="chỉ in câu trả lời, không in trace")
    summary = sub.add_parser("summary", help="báo cáo thu chi (không qua LLM)")
    summary.add_argument("period", nargs="?", default="this_month", choices=get_args(Period))
    lst = sub.add_parser("list", help="giao dịch gần nhất")
    lst.add_argument("limit", nargs="?", type=int, default=20)

    args = parser.parse_args()
    if args.command == "chat":
        cmd_chat(args.quiet)
    elif args.command == "summary":
        cmd_summary(args.period)
    else:
        cmd_list(args.limit)


if __name__ == "__main__":
    main()
