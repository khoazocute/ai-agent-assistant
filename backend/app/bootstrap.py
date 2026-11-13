"""Khởi tạo những thứ dùng chung khi app chạy: DB đã có bảng + dữ liệu mặc định."""

from __future__ import annotations

from app.config import get_settings
from app.db.session import SessionFactory, init_db, make_engine, make_session_factory, session_scope
from app.services.finance_service import FinanceService


def setup_database(url: str | None = None) -> SessionFactory:
    """`url=None` → lấy từ .env. Test truyền "sqlite://" (DB trong RAM, mỗi lần chạy là DB mới)."""
    engine = make_engine(url or get_settings().resolved_database_url)
    init_db(engine)
    factory = make_session_factory(engine)
    with session_scope(factory) as s:
        FinanceService(s).seed_default_categories()
    return factory
