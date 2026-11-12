"""Nghiệp vụ thuần: finance, schedule, email, briefing, receipt.

Agent tool và web API cùng gọi lớp này → một nguồn sự thật, không lặp code (ADR-0004, bước 4).
Sau mỗi lần ghi DB, service phát sự kiện cho website cập nhật realtime (bước 14).
"""
