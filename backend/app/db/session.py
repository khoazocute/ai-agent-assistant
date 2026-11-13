"""Kết nối DB và quản lý phiên (session).

- `make_engine(url)`: SQLite cần `check_same_thread=False` vì ToolExecutor chạy tool trong thread pool.
- `session_scope(factory)`: MỘT đơn vị công việc — thành công thì commit, lỗi thì rollback, luôn đóng.
- `init_db(engine)`: tạo bảng. Khi chuyển PostgreSQL (bước 13) thay bằng Alembic migration.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base

SessionFactory = sessionmaker[Session]


def make_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url)
    in_memory = url in ("sqlite://", "sqlite:///:memory:")
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        # DB trong RAM chỉ tồn tại trong MỘT kết nối → mọi session phải dùng chung kết nối đó (dùng cho test).
        poolclass=StaticPool if in_memory else None,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):  # SQLite mặc định TẮT kiểm tra khoá ngoại
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine: Engine) -> SessionFactory:
    # expire_on_commit=False: đọc được thuộc tính object sau khi commit mà không truy vấn lại.
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: SessionFactory) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(engine: Engine) -> None:
    """Tạo bảng còn thiếu. Dữ liệu ban đầu (danh mục) do service nạp — xem app/bootstrap.py."""
    db_file = engine.url.database
    if engine.url.drivername.startswith("sqlite") and db_file and db_file != ":memory:":
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
