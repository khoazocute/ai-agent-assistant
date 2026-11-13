"""Nghiệp vụ tài chính cá nhân — KHÔNG biết gì về LLM.

Agent tool (agents/finance/tools.py), CLI và web API (bước 13) đều gọi lớp này → một nguồn sự thật.
Mọi con số (tổng, chi ròng, %) do code tính — LLM chỉ hiểu yêu cầu và diễn đạt kết quả (ADR-0004).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Literal, get_args

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import today_vn
from app.db.models import Category, CategoryKind, Transaction

CategoryKey = Literal["an_uong", "di_chuyen", "mua_sam", "giai_tri", "khac", "thu_nhap", "phu_cap_gia_dinh"]

DEFAULT_CATEGORIES: dict[str, tuple[str, CategoryKind]] = {
    "an_uong": ("Ăn uống", CategoryKind.EXPENSE),
    "di_chuyen": ("Di chuyển", CategoryKind.EXPENSE),
    "mua_sam": ("Mua sắm", CategoryKind.EXPENSE),
    "giai_tri": ("Giải trí", CategoryKind.EXPENSE),
    "khac": ("Khác", CategoryKind.EXPENSE),
    "thu_nhap": ("Thu nhập", CategoryKind.INCOME),
    "phu_cap_gia_dinh": ("Phụ cấp gia đình", CategoryKind.INCOME),
}
assert set(DEFAULT_CATEGORIES) == set(get_args(CategoryKey)), "CategoryKey và DEFAULT_CATEGORIES phải khớp"

Period = Literal["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "this_year"]


class FinanceError(ValueError):
    """Lỗi nghiệp vụ — thông điệp viết cho người (và model) đọc để sửa."""


# ---------- Kết quả trả ra (pydantic → JSON được cho tool, API, CLI) ----------

class TransactionOut(BaseModel):
    id: int
    amount_vnd: int
    category: str
    category_name: str
    kind: CategoryKind
    occurred_on: date
    note: str

    @classmethod
    def of(cls, t: Transaction) -> TransactionOut:
        return cls(id=t.id, amount_vnd=t.amount_vnd, category=t.category_key, category_name=t.category.name_vi,
                   kind=t.category.kind, occurred_on=t.occurred_on, note=t.note)


class CategoryTotal(BaseModel):
    category: str
    category_name: str
    kind: CategoryKind
    amount_vnd: int
    count: int
    percent_of_expense: float | None  # chỉ có với khoản chi


class Summary(BaseModel):
    start: date
    end: date
    total_expense_vnd: int
    total_income_vnd: int
    net_spending_vnd: int  # = chi − thu; âm nghĩa là thu nhiều hơn chi
    transaction_count: int
    by_category: list[CategoryTotal]


# ---------- Khoảng thời gian: code tính, không để LLM tự cộng trừ ngày ----------

def resolve_period(period: Period, today: date) -> tuple[date, date]:
    """Trả về (start, end) — cả hai đầu đều TÍNH. Tuần bắt đầu từ thứ Hai."""
    if period == "today":
        return today, today
    if period == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)
    if period == "this_month":
        start = today.replace(day=1)
        return start, _month_end(start)
    if period == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == "this_year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    raise FinanceError(f"Không hiểu khoảng thời gian '{period}'.")


def _month_end(first_day: date) -> date:
    next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


# ---------- Service ----------

class FinanceService:
    def __init__(self, session: Session, today: Callable[[], date] = today_vn) -> None:
        self.s = session
        self.today = today  # tiêm vào được → test cố định "hôm nay", không phụ thuộc đồng hồ thật

    def seed_default_categories(self) -> None:
        existing = set(self.s.scalars(select(Category.key)))
        self.s.add_all(Category(key=k, name_vi=name, kind=kind)
                       for k, (name, kind) in DEFAULT_CATEGORIES.items() if k not in existing)
        self.s.flush()

    def add_transaction(
        self, amount_vnd: int, category: str, occurred_on: date | None = None, note: str = ""
    ) -> TransactionOut:
        if amount_vnd <= 0:
            raise FinanceError("Số tiền phải là số nguyên dương (VND). Thu hay chi do danh mục quyết định.")
        cat = self.s.get(Category, category)
        if cat is None:
            raise FinanceError(f"Không có danh mục '{category}'. Danh mục hợp lệ: {', '.join(DEFAULT_CATEGORIES)}.")
        occurred_on = occurred_on or self.today()
        if occurred_on > self.today():
            # Thường là model nhầm năm/tháng — chặn để không làm lệch báo cáo.
            raise FinanceError(f"Ngày {occurred_on.isoformat()} ở tương lai; chỉ ghi khoản đã phát sinh.")
        t = Transaction(amount_vnd=amount_vnd, category=cat, occurred_on=occurred_on, note=note.strip())
        self.s.add(t)
        self.s.flush()  # để có id
        return TransactionOut.of(t)

    def list_transactions(
        self, start: date | None = None, end: date | None = None, category: str | None = None, limit: int = 20
    ) -> list[TransactionOut]:
        q = select(Transaction).order_by(Transaction.occurred_on.desc(), Transaction.id.desc()).limit(limit)
        if start:
            q = q.where(Transaction.occurred_on >= start)
        if end:
            q = q.where(Transaction.occurred_on <= end)
        if category:
            q = q.where(Transaction.category_key == category)
        return [TransactionOut.of(t) for t in self.s.scalars(q)]

    def get_summary(self, start: date, end: date) -> Summary:
        if start > end:
            raise FinanceError(f"Ngày bắt đầu {start} sau ngày kết thúc {end}.")
        rows = self.s.execute(
            select(Category, func.sum(Transaction.amount_vnd), func.count(Transaction.id))
            .join(Transaction, Transaction.category_key == Category.key)
            .where(Transaction.occurred_on.between(start, end))
            .group_by(Category.key)
        ).all()
        expense = sum(total for cat, total, _ in rows if cat.kind == CategoryKind.EXPENSE)
        income = sum(total for cat, total, _ in rows if cat.kind == CategoryKind.INCOME)
        by_category = sorted(
            (CategoryTotal(
                category=cat.key, category_name=cat.name_vi, kind=cat.kind, amount_vnd=total, count=count,
                percent_of_expense=(round(total * 100 / expense, 1)
                                    if cat.kind == CategoryKind.EXPENSE and expense else None),
            ) for cat, total, count in rows),
            key=lambda c: (c.kind != CategoryKind.EXPENSE, -c.amount_vnd, c.category),  # thứ tự xác định
        )
        return Summary(start=start, end=end, total_expense_vnd=expense, total_income_vnd=income,
                       net_spending_vnd=expense - income, transaction_count=sum(c.count for c in by_category),
                       by_category=by_category)

    def delete_transaction(self, transaction_id: int) -> TransactionOut:
        t = self.s.get(Transaction, transaction_id)
        if t is None:
            raise FinanceError(f"Không có giao dịch #{transaction_id}.")
        out = TransactionOut.of(t)
        self.s.delete(t)
        return out
