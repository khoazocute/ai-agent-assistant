"""Cấu hình ứng dụng — đọc từ `.env` ở thư mục gốc, một chỗ duy nhất (pydantic-settings).

Vì sao không `os.environ[...]` rải rác: sai tên biến / thiếu biến được phát hiện ngay khi khởi động,
có kiểu dữ liệu và giá trị mặc định rõ ràng, test có thể truyền Settings riêng.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "backend" / "config"
DATA_DIR = ROOT / "backend" / "data"
TRACE_DIR = DATA_DIR / "traces"

# Asia/Ho_Chi_Minh không có giờ mùa hè → +7 cố định (tránh phụ thuộc gói tzdata trên Windows).
VN_TZ = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    database_url: str = "sqlite:///backend/data/app.db"
    fernet_key: str = ""  # mã hoá token OAuth (bước 10)
    default_agent: str = "supervisor"  # agent trả lời Telegram/web (ADR-0008)
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""  # danh sách chat_id, cách nhau bằng dấu phẩy
    telegram_webhook_secret: str = ""
    web_password: str = ""  # mật khẩu đăng nhập website (một chủ sở hữu)
    jwt_secret: str = ""  # ≥ 32 ký tự ngẫu nhiên
    cookie_secure: bool = False  # True khi chạy HTTPS (production)
    # Chạy bot Telegram NGAY TRONG tiến trình web: off | polling (dev) | webhook (production, bước 20)
    telegram_mode: str = "off"
    public_base_url: str = ""  # https://ten-mien-cua-ban — cần cho webhook Telegram

    @property
    def allowed_chat_ids(self) -> set[int]:
        return {int(x) for x in self.telegram_allowed_chat_ids.replace(" ", "").split(",") if x}

    @property
    def resolved_database_url(self) -> str:
        """Đường dẫn SQLite tương đối được tính từ thư mục gốc dự án, không phụ thuộc chỗ đứng khi chạy lệnh."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix) and not self.database_url.startswith(prefix + "/"):
            path = Path(self.database_url.removeprefix(prefix))
            if not path.is_absolute():
                return prefix + (ROOT / path).as_posix()
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


def today_vn() -> date:
    return now_vn().date()
