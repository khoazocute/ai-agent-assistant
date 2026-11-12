"""Kiểm tra tối thiểu: package import được. Giúp CI có việc để chạy ngay từ bước 0."""

import app


def test_package_imports():
    assert app.__version__
