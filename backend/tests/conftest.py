import os
from datetime import date, datetime

import pytest

from app.bootstrap import setup_database
from app.config import VN_TZ

# "Hôm nay" cố định cho mọi test: Thứ Sáu 13/11/2026 → kết quả không phụ thuộc ngày chạy test.
TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 12, 30, tzinfo=VN_TZ)


@pytest.fixture
def session_factory():
    """Mỗi test một DB mới, đã có bảng + danh mục mặc định.
    Mặc định SQLite trong RAM; đặt TEST_DATABASE_URL=postgresql+psycopg://… để chạy cùng bộ test trên
    PostgreSQL (CI làm vậy) — bắt lỗi chỉ xuất hiện ở DB thật (kiểu dữ liệu, ràng buộc, SQL riêng)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return setup_database("sqlite://")
    from app.db.models import Base
    from app.db.session import make_engine
    from app.harness.storage import HarnessBase, init_harness_tables

    engine = make_engine(url)
    init_harness_tables(engine)  # nạp đủ model của harness trước khi xoá
    HarnessBase.metadata.drop_all(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()
    return setup_database(url)
