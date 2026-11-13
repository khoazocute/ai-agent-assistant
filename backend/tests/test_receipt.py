"""Ảnh hóa đơn → đề xuất → người dùng xác nhận → ghi sổ (LLM giả trả JSON theo schema)."""

from datetime import date

import pytest
from fakes import FakeLLM
from fastapi.testclient import TestClient

from app.agents.receipt.workflow import RECEIPT_SCHEMA, ReceiptError, _validate, read_receipt
from app.db.session import session_scope
from app.harness.agentops.store import recent_runs
from app.integrations.email_provider import FakeEmailProvider
from app.runtime import Runtime
from app.services.finance_service import FinanceService

TODAY = date(2026, 11, 14)
PHO = {"readable": True, "merchant": "Phở Thìn", "date": "2026-11-13", "total_vnd": 125000, "category": "an_uong",
       "items": [{"name": "Phở bò", "amount_vnd": 65000}, {"name": "Phở gà", "amount_vnd": 60000}]}
JPEG = b"\xff\xd8\xff" + b"0" * 100


@pytest.mark.parametrize(("data", "expected"), [
    (PHO, (True, 125000, "an_uong", date(2026, 11, 13), [])),
    ({**PHO, "readable": False, "total_vnd": 0}, (False, 0, "an_uong", date(2026, 11, 13), [])),
    ({**PHO, "total_vnd": -5}, (False, 0, "an_uong", date(2026, 11, 13), [])),
    ({**PHO, "category": "thu_nhap"}, (True, 125000, "khac", date(2026, 11, 13), ["danh mục"])),  # không cho "thu"
    ({**PHO, "date": "2027-01-01"}, (True, 125000, "an_uong", TODAY, ["tương lai"])),
    ({**PHO, "date": "13/11"}, (True, 125000, "an_uong", TODAY, ["ngày"])),
    ({**PHO, "total_vnd": 900000}, (True, 900000, "an_uong", date(2026, 11, 13), ["lệch"])),
])
def test_model_output_is_validated_by_code(data, expected):
    p = _validate(data, TODAY)
    readable, total, category, day, warn_words = expected
    assert (p.readable, p.total_vnd, p.category, p.occurred_on) == (readable, total, category, day)
    assert len(p.warnings) == len(warn_words) and all(w in " ".join(p.warnings) for w in warn_words)


def test_schema_only_allows_expense_categories():
    assert "thu_nhap" not in RECEIPT_SCHEMA["properties"]["category"]["enum"]


def test_rejects_bad_files_before_calling_llm():
    llm = FakeLLM([])
    with pytest.raises(ReceiptError, match="không hỗ trợ"):
        read_receipt(llm, JPEG, "application/pdf", TODAY)
    with pytest.raises(ReceiptError, match="5 MB"):
        read_receipt(llm, b"0" * (5 * 1024 * 1024 + 1), "image/jpeg", TODAY)
    assert llm.seen_histories == []  # không tốn request


def test_propose_then_approve_writes_exactly_what_was_shown():
    rt = Runtime.create("sqlite://", email_provider=FakeEmailProvider(), llm=FakeLLM([PHO]))
    proposal, pending = rt.propose_receipt(JPEG, "image/jpeg", "telegram")
    assert rt.llm.seen_histories[0][0]["image"] is True
    assert "125.000đ · Ăn uống · 13/11/2026 · Phở Thìn" in pending.summary
    with session_scope(rt.session_factory) as s:
        assert FinanceService(s).list_transactions() == []  # chưa ghi khi chưa xác nhận

    assert rt.approve(pending.id, "user:test").status == "executed"
    with session_scope(rt.session_factory) as s:
        (t,) = FinanceService(s).list_transactions()
    assert (t.amount_vnd, t.category, t.occurred_on, t.note) == (125000, "an_uong", date(2026, 11, 13),
                                                                 "Phở Thìn (hóa đơn)")
    assert [r.agent for r in recent_runs(rt.session_factory)] == ["receipt"]  # có trace như mọi run


def test_unreadable_receipt_creates_nothing():
    rt = Runtime.create("sqlite://", email_provider=FakeEmailProvider(),
                        llm=FakeLLM([{"readable": False, "total_vnd": 0, "category": "khac"}]))
    proposal, pending = rt.propose_receipt(JPEG, "image/png", "web")
    assert pending is None and rt.approvals.list("pending") == []


def test_upload_api(monkeypatch, tmp_path):
    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("WEB_PASSWORD", "pw")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    get_settings.cache_clear()
    rt = Runtime.create(f"sqlite:///{(tmp_path / 'r.db').as_posix()}", email_provider=FakeEmailProvider(),
                        llm=FakeLLM([PHO]))
    client = TestClient(create_app(rt))
    client.post("/api/auth/login", json={"password": "pw"})
    r = client.post("/api/finance/receipts", files={"file": ("hd.jpg", JPEG, "image/jpeg")}).json()
    assert r["proposal"]["total_vnd"] == 125000 and r["approval"]["status"] == "pending"
    bad = client.post("/api/finance/receipts", files={"file": ("x.pdf", b"%PDF", "application/pdf")})
    assert bad.status_code == 400
    get_settings.cache_clear()
