"""API chi tiêu — gọi CÙNG FinanceService với agent (ADR-0004): web và agent luôn ra cùng con số."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db, get_runtime, require_user
from app.db.models import Category
from app.runtime import Runtime
from app.services.finance_service import CategoryKey, FinanceService, Period, Summary, TransactionOut, resolve_period

router = APIRouter(prefix="/api/finance", tags=["finance"], dependencies=[Depends(require_user)])


class TransactionIn(BaseModel):
    amount_vnd: int = Field(gt=0)
    category: CategoryKey
    occurred_on: date | None = None
    note: str = Field("", max_length=200)


@router.get("/categories")
def categories(s: Session = Depends(db)) -> list[dict]:
    return [{"key": c.key, "name": c.name_vi, "kind": c.kind} for c in s.scalars(select(Category))]


@router.get("/summary")
def summary(period: Period = "this_month", s: Session = Depends(db)) -> Summary:
    svc = FinanceService(s)
    return svc.get_summary(*resolve_period(period, svc.today()))


@router.get("/transactions")
def transactions(limit: int = 50, start: date | None = None, end: date | None = None,
                 category: CategoryKey | None = None, s: Session = Depends(db)) -> list[TransactionOut]:
    return FinanceService(s).list_transactions(start, end, category, min(limit, 500))


@router.post("/transactions")
def add(body: TransactionIn, s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> TransactionOut:
    t = FinanceService(s).add_transaction(body.amount_vnd, body.category, body.occurred_on, body.note)
    rt.audit.record("user:web", "web:add_transaction", f"transaction#{t.id}", body.model_dump(mode="json"), session=s)
    return t


@router.delete("/transactions/{transaction_id}")
def delete(transaction_id: int, s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> TransactionOut:
    # Người dùng tự bấm xoá trên web (có hộp xác nhận ở giao diện) = chính họ quyết định → không cần duyệt
    # thêm, nhưng vẫn ghi audit. Luồng duyệt dành cho hành động do AGENT đề xuất.
    t = FinanceService(s).delete_transaction(transaction_id)
    rt.audit.record("user:web", "web:delete_transaction", f"transaction#{t.id}", t.model_dump(mode="json"), session=s)
    return t
