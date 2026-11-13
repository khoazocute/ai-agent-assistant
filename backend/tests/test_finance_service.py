"""Nghiệp vụ tài chính — test thuần, không LLM. Đây là phần PHẢI đúng 100%: con số do code tính."""

from datetime import date

import pytest
from conftest import TODAY
from sqlalchemy.exc import IntegrityError

from app.db.models import Transaction
from app.db.session import session_scope
from app.services.finance_service import FinanceError, FinanceService, resolve_period


@pytest.fixture
def svc(session_factory):
    with session_scope(session_factory) as s:
        yield FinanceService(s, today=lambda: TODAY)


def test_add_defaults_to_today_and_returns_category_info(svc):
    t = svc.add_transaction(45_000, "an_uong", note=" phở bò ")
    assert (t.amount_vnd, t.category_name, t.kind, t.occurred_on, t.note) == (
        45_000, "Ăn uống", "expense", TODAY, "phở bò")


@pytest.mark.parametrize(("amount", "category", "on", "message"), [
    (0, "an_uong", None, "nguyên dương"),
    (-5_000, "an_uong", None, "nguyên dương"),
    (10_000, "an_vat", None, "Không có danh mục"),
    (10_000, "an_uong", date(2027, 11, 13), "tương lai"),
])
def test_add_rejects_bad_input_with_readable_message(svc, amount, category, on, message):
    with pytest.raises(FinanceError, match=message):
        svc.add_transaction(amount, category, on)


def test_db_itself_rejects_non_positive_amount(svc):
    # Lớp bảo vệ thứ hai: kể cả khi ai đó bỏ qua service và ghi thẳng vào DB.
    svc.s.add(Transaction(amount_vnd=0, category_key="khac", occurred_on=TODAY))
    with pytest.raises(IntegrityError):
        svc.s.flush()
    svc.s.rollback()  # phiên hỏng sau lỗi flush — dọn để fixture đóng phiên sạch sẽ


def test_summary_net_spending_is_expense_minus_income(svc):
    svc.add_transaction(45_000, "an_uong")
    svc.add_transaction(55_000, "an_uong")
    svc.add_transaction(100_000, "di_chuyen")
    svc.add_transaction(150_000, "phu_cap_gia_dinh")
    svc.add_transaction(999_000, "mua_sam", date(2026, 10, 31))  # ngoài khoảng → không tính

    r = svc.get_summary(date(2026, 11, 1), date(2026, 11, 30))
    assert (r.total_expense_vnd, r.total_income_vnd, r.net_spending_vnd) == (200_000, 150_000, 50_000)
    assert r.transaction_count == 4
    # Chi xếp trước (lớn → nhỏ, bằng nhau thì theo tên khoá), thu xếp sau; % chỉ tính trên tổng chi.
    assert [(c.category, c.amount_vnd, c.percent_of_expense) for c in r.by_category] == [
        ("an_uong", 100_000, 50.0), ("di_chuyen", 100_000, 50.0), ("phu_cap_gia_dinh", 150_000, None),
    ]


def test_summary_can_be_negative_when_income_exceeds_spending(svc):
    svc.add_transaction(10_000_000, "thu_nhap")
    svc.add_transaction(30_000, "an_uong")
    r = svc.get_summary(TODAY, TODAY)
    assert r.net_spending_vnd == -9_970_000


def test_empty_summary_has_no_division_by_zero(svc):
    r = svc.get_summary(TODAY, TODAY)
    assert (r.total_expense_vnd, r.net_spending_vnd, r.by_category) == (0, 0, [])


def test_list_is_newest_first_and_filterable(svc):
    a = svc.add_transaction(1_000, "an_uong", date(2026, 11, 1))
    b = svc.add_transaction(2_000, "di_chuyen", date(2026, 11, 10))
    c = svc.add_transaction(3_000, "an_uong", date(2026, 11, 12))
    assert [t.id for t in svc.list_transactions()] == [c.id, b.id, a.id]
    assert [t.id for t in svc.list_transactions(category="an_uong")] == [c.id, a.id]
    assert [t.id for t in svc.list_transactions(start=date(2026, 11, 5), end=date(2026, 11, 11))] == [b.id]
    assert len(svc.list_transactions(limit=2)) == 2


def test_delete(svc):
    t = svc.add_transaction(1_000, "khac")
    assert svc.delete_transaction(t.id).id == t.id
    assert svc.list_transactions() == []
    with pytest.raises(FinanceError, match="Không có giao dịch"):
        svc.delete_transaction(t.id)


@pytest.mark.parametrize(("period", "expected"), [
    ("today", (date(2026, 11, 13), date(2026, 11, 13))),
    ("yesterday", (date(2026, 11, 12), date(2026, 11, 12))),
    ("this_week", (date(2026, 11, 9), date(2026, 11, 15))),  # 13/11/2026 là thứ Sáu → tuần từ thứ Hai 9/11
    ("last_week", (date(2026, 11, 2), date(2026, 11, 8))),
    ("this_month", (date(2026, 11, 1), date(2026, 11, 30))),
    ("last_month", (date(2026, 10, 1), date(2026, 10, 31))),
    ("this_year", (date(2026, 1, 1), date(2026, 12, 31))),
])
def test_resolve_period(period, expected):
    assert resolve_period(period, TODAY) == expected


def test_resolve_period_across_year_and_february():
    assert resolve_period("last_month", date(2027, 1, 5)) == (date(2026, 12, 1), date(2026, 12, 31))
    assert resolve_period("this_month", date(2028, 2, 10)) == (date(2028, 2, 1), date(2028, 2, 29))  # năm nhuận
