"""Khởi tạo những thứ dùng chung khi app chạy: DB đã có bảng + dữ liệu mặc định, tracer, LLM."""

from __future__ import annotations

from app.config import CONFIG_DIR, TRACE_DIR, get_settings
from app.db.session import SessionFactory, init_db, make_engine, make_session_factory, session_scope
from app.harness.agentops.cost import Pricing
from app.harness.agentops.store import DbTraceSink
from app.harness.agentops.tracer import Tracer
from app.harness.storage import init_harness_tables
from app.services.finance_service import FinanceService


def setup_database(url: str | None = None) -> SessionFactory:
    """`url=None` → lấy từ .env. Test truyền "sqlite://" (DB trong RAM, mỗi lần chạy là DB mới)."""
    engine = make_engine(url or get_settings().resolved_database_url)
    init_db(engine)
    init_harness_tables(engine)
    factory = make_session_factory(engine)
    with session_scope(factory) as s:
        FinanceService(s).seed_default_categories()
    return factory


def load_pricing() -> Pricing:
    return Pricing.load(CONFIG_DIR / "pricing.yaml")


def make_tracer(factory: SessionFactory, channel: str, console: bool = False) -> Tracer:
    """Tracer chuẩn của app: file JSONL + DB (+ console nếu muốn xem trực tiếp)."""
    return Tracer(directory=TRACE_DIR, console=console, sinks=[DbTraceSink(factory, load_pricing(), channel)])


def make_llm(model: str | None = None):
    from app.harness.orchestration.llm_client import GeminiClient

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY trong .env")
    return GeminiClient(api_key=settings.gemini_api_key, model=model or settings.gemini_model)
