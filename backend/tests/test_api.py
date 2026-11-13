"""Web API qua TestClient: đăng nhập, bảo vệ route, CRUD, duyệt, run, chat (LLM giả)."""

import pytest
from fakes import FakeLLM
from fastapi.testclient import TestClient

from app.config import get_settings
from app.harness.orchestration.llm_client import ToolCall
from app.integrations.email_provider import FakeEmailProvider
from app.main import create_app
from app.runtime import Runtime

PASSWORD = "mat-khau-thu-nghiem"


@pytest.fixture
def make_client(monkeypatch, tmp_path):
    monkeypatch.setenv("WEB_PASSWORD", PASSWORD)
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    get_settings.cache_clear()

    def build(script=()):
        # DB dạng FILE (không phải RAM): bắt được lỗi tranh khoá ghi giữa các phiên như khi chạy thật.
        db_url = f"sqlite:///{(tmp_path / f'api{len(list(tmp_path.iterdir()))}.db').as_posix()}"
        rt = Runtime.create(db_url, email_provider=FakeEmailProvider(), llm=FakeLLM(list(script)))
        return TestClient(create_app(rt)), rt

    yield build
    get_settings.cache_clear()


def login(client: TestClient) -> None:
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 200


def test_protected_routes_need_login(make_client):
    client, _ = make_client()
    assert client.get("/api/finance/summary").status_code == 401
    assert client.get("/api/approvals").status_code == 401
    assert client.post("/api/auth/login", json={"password": "sai"}).status_code == 401
    login(client)
    assert client.get("/api/auth/me").json() == {"user": "owner"}
    cookie = client.cookies.get("session")
    assert cookie and "httponly" in str(client.post("/api/auth/login", json={"password": PASSWORD})
                                         .headers.get("set-cookie", "")).lower()


def test_login_rate_limited(make_client):
    from app.api.auth import limiter

    client, _ = make_client()
    limiter.reset("testclient")
    for _ in range(5):
        client.post("/api/auth/login", json={"password": "sai"})
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 429
    limiter.reset("testclient")


def test_login_refused_when_not_configured(make_client, monkeypatch):
    client, _ = make_client()
    monkeypatch.setenv("WEB_PASSWORD", "")
    get_settings.cache_clear()
    assert client.post("/api/auth/login", json={"password": ""}).status_code == 503


def test_finance_crud_and_business_errors(make_client):
    client, rt = make_client()
    login(client)
    r = client.post("/api/finance/transactions", json={"amount_vnd": 45000, "category": "an_uong", "note": "phở"})
    assert r.status_code == 200
    assert client.post("/api/finance/transactions", json={"amount_vnd": -1, "category": "an_uong"}).status_code == 422
    assert client.get("/api/finance/summary").json()["total_expense_vnd"] == 45000
    assert len(client.get("/api/finance/categories").json()) == 7
    assert client.delete(f"/api/finance/transactions/{r.json()['id']}").status_code == 200
    assert client.delete("/api/finance/transactions/999").status_code == 400  # lỗi nghiệp vụ → 400
    assert [e.action for e in rt.audit.recent()] == ["web:delete_transaction", "web:add_transaction"]


def test_events_and_schedule(make_client):
    client, _ = make_client()
    login(client)
    body = {"title": "Họp", "start_at": "2026-12-01T09:00", "end_at": "2026-12-01T10:00"}
    assert client.post("/api/events", json=body).status_code == 200
    events = client.get("/api/events", params={"start": "2026-12-01", "end": "2026-12-01"}).json()
    assert [e["title"] for e in events] == ["Họp"]
    client.post("/api/tasks", json={"title": "Học", "duration_min": 60})
    plan = client.post("/api/schedule/suggest", json={"start": "2026-12-01", "end": "2026-12-01"}).json()
    created = client.post(f"/api/schedule/plans/{plan['plan_id']}/apply").json()
    assert created[0]["title"] == "Học"


def test_chat_creates_approval_then_approve_via_api(make_client):
    client, rt = make_client([
        [ToolCall("a", "ask_finance_agent", {"request": "xoá giao dịch số 1"})],
        [ToolCall("d", "delete_transaction", {"transaction_id": 1})],
        "Đã tạo yêu cầu duyệt.",
        "Mình đã tạo yêu cầu xoá, bạn duyệt giúp nhé.",
    ])
    login(client)
    client.post("/api/finance/transactions", json={"amount_vnd": 45000, "category": "an_uong"})
    reply = client.post("/api/chat", json={"message": "xoá giao dịch số 1"}).json()
    assert reply["status"] == "ok" and reply["tools_used"] == ["ask_finance_agent", "delete_transaction"]
    (pending,) = reply["approvals"]
    assert client.get("/api/finance/summary").json()["total_expense_vnd"] == 45000  # chưa xoá

    done = client.post(f"/api/approvals/{pending['id']}/approve").json()
    assert done["status"] == "executed"
    assert client.get("/api/finance/summary").json()["total_expense_vnd"] == 0
    assert client.post(f"/api/approvals/{pending['id']}/approve").status_code == 409

    runs = client.get("/api/runs").json()
    detail = client.get(f"/api/runs/{runs[0]['run_id']}").json()
    assert detail["run"]["agent"] == "supervisor" and detail["children"][0]["agent"] == "finance"
    assert detail["events"][0]["type"] == "run_start" and "system" in detail["events"][0]["data"]
    assert client.get("/api/metrics").json()["pending_approvals"] == 0
    assert client.post("/api/chat/feedback", json={"run_id": reply["run_id"], "rating": 1}).json() == {"ok": True}


def test_health(make_client):
    client, _ = make_client()
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
