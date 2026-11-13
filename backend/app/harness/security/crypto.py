"""Mã hoá bí mật lưu trên đĩa (token OAuth Google…) bằng Fernet (AES + HMAC).

Không có FERNET_KEY → từ chối lưu bí mật dạng rõ (fail closed), báo cách tạo khoá:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations


class SecretBox:
    def __init__(self, key: str) -> None:
        if not key:
            raise RuntimeError(
                "Thiếu FERNET_KEY trong .env — tạo bằng: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"")
        from cryptography.fernet import Fernet

        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, token: bytes) -> str:
        return self._fernet.decrypt(token).decode("utf-8")
