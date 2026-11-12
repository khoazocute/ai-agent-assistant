"""Security Harness — bảo vệ hệ thống và dữ liệu cá nhân.

- sanitizer.py  bọc nội dung ngoài trong <untrusted_content>, chống prompt injection (bước 10)
- pii.py        phát hiện thông tin nhạy cảm trong mail sắp gửi                    (bước 10)
- crypto.py     mã hoá token OAuth (Fernet)                                          (bước 10)
- auth.py       JWT cho web, allowlist chat_id Telegram                              (bước 12–13)
"""
