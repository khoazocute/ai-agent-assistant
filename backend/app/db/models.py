"""Bảng dữ liệu (SQLAlchemy 2, kiểu khai báo có type hint).

Quy ước:
- Tiền là **số nguyên VND** (`amount_vnd: int`), luôn dương. Thu hay chi do `Category.kind` quyết định,
  không dùng số âm — tránh lỗi dấu và lỗi làm tròn của float.
- Ngày giao dịch (`occurred_on`) là ngày theo giờ Việt Nam; `created_at` là thời điểm ghi (có múi giờ).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import now_vn


class Base(DeclarativeBase):
    pass


class CategoryKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


class Category(Base):
    __tablename__ = "categories"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)  # vd. "an_uong" — ổn định, dùng trong tool
    name_vi: Mapped[str] = mapped_column(String(80))  # vd. "Ăn uống" — để hiển thị
    kind: Mapped[CategoryKind] = mapped_column(String(10))


class Transaction(Base):
    __tablename__ = "transactions"
    # Luật ở tầng DB: kể cả code có bug, DB vẫn không nhận số tiền <= 0.
    __table_args__ = (CheckConstraint("amount_vnd > 0", name="ck_transactions_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    amount_vnd: Mapped[int]
    category_key: Mapped[str] = mapped_column(ForeignKey("categories.key"), index=True)
    occurred_on: Mapped[date] = mapped_column(index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(default=now_vn)

    category: Mapped[Category] = relationship(lazy="joined")
