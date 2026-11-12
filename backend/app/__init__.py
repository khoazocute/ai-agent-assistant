"""Trợ lý cá nhân multi-agent ReAct.

Bản đồ thư mục:
- harness/      7 harness dùng chung, KHÔNG phụ thuộc nghiệp vụ (tái sử dụng được cho dự án khác)
- agents/       từng agent: AGENT.md (spec), prompt.md (system prompt), tools.py
- services/     nghiệp vụ thuần (dùng chung cho agent và web API)
- integrations/ Gmail, Google Calendar, Telegram, speech-to-text
- api/          REST API (FastAPI)
- jobs/         việc chạy định kỳ (nhắc lịch, kéo mail, bản tin)
- db/           model SQLAlchemy và migration
"""

__version__ = "0.0.1"
