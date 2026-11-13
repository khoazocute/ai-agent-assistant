"""Đăng nhập Google (OAuth) cho Gmail + Calendar — chạy MỘT lần trên máy của bạn.

    python -m app.integrations.google_auth

Chuẩn bị (xem README → "Kết nối Google"):
  1. Google Cloud Console → tạo project → bật Gmail API + Google Calendar API.
  2. OAuth consent screen (External, thêm email của bạn làm Test user).
  3. Credentials → OAuth client ID → loại **Desktop app** → tải JSON về `backend/data/google_client_secret.json`.
  4. `.env`: FERNET_KEY=<khoá> (token được mã hoá trước khi lưu).

Token lưu ở `backend/data/google_token.enc` (đã mã hoá, nằm trong thư mục không commit).
Scopes tối thiểu: đọc mail, soạn nháp, gửi mail, sửa sự kiện lịch — không xin quyền xoá hộp thư.
"""

from __future__ import annotations

import json
import os
import sys

from app.config import DATA_DIR, get_settings
from app.harness.security.crypto import SecretBox

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]
CLIENT_SECRET = DATA_DIR / "google_client_secret.json"
TOKEN_FILE = DATA_DIR / "google_token.enc"


def _box() -> SecretBox:
    return SecretBox(os.environ.get("FERNET_KEY") or get_settings().fernet_key)


def is_connected() -> bool:
    return TOKEN_FILE.exists()


def load_credentials():
    """Credentials hợp lệ (tự refresh khi hết hạn) hoặc None nếu chưa đăng nhập."""
    if not TOKEN_FILE.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    box = _box()
    creds = Credentials.from_authorized_user_info(json.loads(box.decrypt(TOKEN_FILE.read_bytes())), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_bytes(box.encrypt(creds.to_json()))
    return creds


def login() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENT_SECRET.exists():
        sys.exit(f"Không thấy {CLIENT_SECRET}. Tải OAuth client (Desktop app) từ Google Cloud Console về đây.")
    box = _box()
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_bytes(box.encrypt(creds.to_json()))
    print(f"Đã lưu token (mã hoá) vào {TOKEN_FILE}")


if __name__ == "__main__":
    login()
