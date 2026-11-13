"""Chống prompt injection: nội dung bên ngoài (email, chữ trong ảnh…) là DỮ LIỆU, không phải chỉ dẫn (ADR-0009).

Ba lớp, không lớp nào đủ một mình:
  1. wrap_untrusted  bọc nội dung trong <untrusted_content> — prompt dặn model không làm theo chỉ dẫn bên trong.
                     Thẻ đóng giả mạo bên trong nội dung bị vô hiệu hoá để kẻ gian không "thoát" ra ngoài.
  2. detect_injection  dò các mẫu câu ra lệnh cho AI → gắn cờ cảnh báo (model + người duyệt đều thấy).
  3. (quan trọng nhất) hành động nguy hiểm như gửi mail bị chặn ở tầng CODE (policy + duyệt) — kể cả khi
     model đã bị lừa hoàn toàn, nó cũng không tự gửi được.
"""

from __future__ import annotations

import re

_TAG = re.compile(r"<\s*(/?)\s*untrusted_content", re.IGNORECASE)

# (mô tả, mẫu) — tiếng Việt + tiếng Anh. Mục tiêu là GẮN CỜ, không phải chặn: nhầm lẫn vô hại.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("yêu cầu bỏ qua chỉ dẫn", re.compile(
        r"(ignore|disregard|forget)\s+(all\s+|any\s+)?(previous|prior|above|earlier|your)\s+(instructions|rules)"
        r"|bỏ\s*qua\s+(mọi|tất\s*cả|các|những)?\s*(hướng\s*dẫn|chỉ\s*dẫn|quy\s*tắc|lệnh)", re.I)),
    ("giả làm hệ thống / đổi vai trò", re.compile(
        r"\b(system\s*prompt|you\s+are\s+now|new\s+instructions|act\s+as)\b"
        r"|bạn\s+(bây\s*giờ\s+)?là\s+(một\s+)?(trợ\s*lý|AI)\s+(mới|khác)|chỉ\s*dẫn\s+mới\s+cho\s+(AI|trợ\s*lý)", re.I)),
    ("thẻ hội thoại giả", re.compile(r"<\s*/?\s*(system|assistant|tool|user)\s*>", re.I)),
    ("yêu cầu chuyển tiếp / gửi dữ liệu ra ngoài", re.compile(
        r"(forward|send|email)\s+(this|all|the|every|your)\b.{0,60}\bto\s+\S+@\S+"
        r"|(chuyển\s*tiếp|gửi)\s.{0,60}(cho|tới|đến|về)\s+\S+@\S+", re.I)),
    ("đòi thông tin bí mật", re.compile(
        r"(password|mật\s*khẩu|OTP|mã\s*xác\s*(thực|nhận)|api\s*key|token)\s.{0,40}(gửi|send|reply|trả\s*lời|cung\s*cấp)"
        r"|(gửi|send|cung\s*cấp)\s.{0,40}(password|mật\s*khẩu|OTP|mã\s*xác\s*(thực|nhận)|api\s*key)", re.I)),
]


def neutralize(text: str) -> str:
    """Vô hiệu hoá thẻ <untrusted_content> / </untrusted_content> nằm SẴN trong nội dung."""
    return _TAG.sub(lambda m: f"&lt;{m.group(1)}untrusted_content", text)


def wrap_untrusted(text: str, source: str) -> str:
    safe_source = re.sub(r"[^\w.#:@-]", "_", source)[:80]
    return f'<untrusted_content source="{safe_source}">\n{neutralize(text)}\n</untrusted_content>'


def detect_injection(text: str) -> list[str]:
    """Danh sách mô tả các dấu hiệu prompt injection tìm thấy (rỗng = không thấy gì đáng ngờ)."""
    return [label for label, pattern in _INJECTION_PATTERNS if pattern.search(text)]
