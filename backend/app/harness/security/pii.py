"""Phát hiện dữ liệu nhạy cảm trong nội dung SẮP GỬI ĐI (email nháp) → cảnh báo trong yêu cầu duyệt.

Không chặn: người dùng có thể chủ ý gửi số tài khoản cho người thân. Mục tiêu là để người duyệt NHÌN THẤY
trước khi bấm gửi — đặc biệt khi bản nháp do AI soạn từ một email lạ.
"""

from __future__ import annotations

import re

_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("số thẻ ngân hàng", re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b")),
    ("dãy số dài (tài khoản / CCCD)", re.compile(r"(?<![\d.,])\d{9,19}(?![\d.,])")),
    ("mã OTP / mã xác thực", re.compile(r"(OTP|mã\s*xác\s*(thực|nhận)|verification\s+code)\D{0,20}\d{4,8}", re.I)),
    ("mật khẩu", re.compile(r"(mật\s*khẩu|password|passwd|\bpass\b)\s*(là|is|:|=)\s*\S+", re.I)),
    ("khoá API / token", re.compile(r"\b(sk|AIza|ghp|xox[bp])[-_A-Za-z0-9]{16,}\b")),
]


def scan_pii(text: str) -> list[str]:
    return [label for label, pattern in _PII_PATTERNS if pattern.search(text)]
