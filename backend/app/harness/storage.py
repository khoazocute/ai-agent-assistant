"""Bảng dữ liệu RIÊNG của harness (trace, duyệt, audit, memory…).

Dùng `HarnessBase` tách khỏi `app.db.models.Base` của nghiệp vụ: harness không import gì từ app/ →
copy nguyên thư mục harness/ sang dự án khác vẫn chạy. Hai bộ bảng dùng chung một engine/DB.
"""

from __future__ import annotations

from sqlalchemy import Engine, MetaData, inspect, text
from sqlalchemy.orm import DeclarativeBase


class HarnessBase(DeclarativeBase):
    pass


def init_harness_tables(engine: Engine) -> None:
    # Import để các model đăng ký vào HarnessBase.metadata trước khi create_all.
    from app.harness.agentops import store  # noqa: F401
    from app.harness.context import memory  # noqa: F401
    from app.harness.evaluation import feedback  # noqa: F401
    from app.harness.governance import audit  # noqa: F401
    from app.harness.orchestration import approvals  # noqa: F401

    HarnessBase.metadata.create_all(engine)
    add_missing_columns(engine, HarnessBase.metadata)


def add_missing_columns(engine: Engine, metadata: MetaData) -> list[str]:
    """create_all KHÔNG sửa bảng đã có → model thêm cột mới thì DB cũ thiếu cột và lỗi khi chạy.
    Ở đây chỉ làm phần an toàn: thêm cột CHO PHÉP RỖNG còn thiếu (dữ liệu cũ nhận NULL). Đổi kiểu,
    đổi tên, xoá cột → cần migration thật (Alembic, khi chuyển PostgreSQL ở bước 20)."""
    inspector = inspect(engine)
    added = []
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                if not column.nullable:
                    raise RuntimeError(f"Bảng {table.name} thiếu cột bắt buộc {column.name} — cần migration.")
                col_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))
                added.append(f"{table.name}.{column.name}")
    return added
