"""Bảng dữ liệu RIÊNG của harness (trace, duyệt, audit, memory…).

Dùng `HarnessBase` tách khỏi `app.db.models.Base` của nghiệp vụ: harness không import gì từ app/ →
copy nguyên thư mục harness/ sang dự án khác vẫn chạy. Hai bộ bảng dùng chung một engine/DB.
"""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase


class HarnessBase(DeclarativeBase):
    pass


def init_harness_tables(engine: Engine) -> None:
    # Import để các model đăng ký vào HarnessBase.metadata trước khi create_all.
    from app.harness.agentops import store  # noqa: F401

    HarnessBase.metadata.create_all(engine)
