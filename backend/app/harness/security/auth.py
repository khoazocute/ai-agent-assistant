"""Xác thực web cho MỘT chủ sở hữu: mật khẩu → JWT trong cookie httpOnly.

- So mật khẩu bằng `hmac.compare_digest` (thời gian hằng — không lộ qua đo thời gian).
- JWT ký HS256, có hạn; cookie httpOnly (JavaScript không đọc được → XSS không lấy được phiên),
  SameSite=Lax (giảm CSRF).
- Giới hạn số lần đăng nhập sai theo IP (chống dò mật khẩu).
- Không cấu hình mật khẩu/secret → từ chối đăng nhập (fail closed), không có "chế độ không mật khẩu".
"""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

import jwt

ALGORITHM = "HS256"


class AuthError(Exception):
    pass


def check_password(given: str, expected: str) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def create_token(secret: str, subject: str, ttl_seconds: int = 7 * 24 * 3600) -> str:
    if len(secret) < 32:
        raise AuthError("JWT_SECRET phải dài ít nhất 32 ký tự.")
    now = int(time.time())
    return jwt.encode({"sub": subject, "iat": now, "exp": now + ttl_seconds}, secret, algorithm=ALGORITHM)


def verify_token(secret: str, token: str) -> str:
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])["sub"]
    except jwt.PyJWTError as e:
        raise AuthError(f"Phiên không hợp lệ: {e}") from e


class LoginRateLimiter:
    """Tối đa `max_failures` lần sai trong `window_seconds` cho mỗi IP."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 300) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def blocked(self, ip: str) -> bool:
        q = self._failures[ip]
        while q and q[0] < time.time() - self.window:
            q.popleft()
        return len(q) >= self.max_failures

    def fail(self, ip: str) -> None:
        self._failures[ip].append(time.time())

    def reset(self, ip: str) -> None:
        self._failures.pop(ip, None)
