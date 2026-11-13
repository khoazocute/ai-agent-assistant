from datetime import date, datetime

import pytest

from app.bootstrap import setup_database
from app.config import VN_TZ

# "Hôm nay" cố định cho mọi test: Thứ Sáu 13/11/2026 → kết quả không phụ thuộc ngày chạy test.
TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 12, 30, tzinfo=VN_TZ)


@pytest.fixture
def session_factory():
    """Mỗi test một DB SQLite mới trong RAM, đã có bảng + danh mục mặc định."""
    return setup_database("sqlite://")
