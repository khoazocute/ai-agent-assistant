"""Security Harness — bảo vệ dữ liệu và chống bị lợi dụng.

- sanitizer.py  wrap_untrusted (<untrusted_content>), detect_injection        (bước 10, ADR-0009)
- pii.py        scan_pii: số thẻ, tài khoản, OTP, mật khẩu trong mail sắp gửi (bước 10)
- crypto.py     mã hoá token OAuth bằng Fernet                                (bước 10)
- auth.py       JWT cho web, allowlist chat_id Telegram                         (bước 12–13)
"""
