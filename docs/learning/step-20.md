# Bước 20 — Đóng gói, triển khai, CI, runbook, playbook
- Ngày: 2026-11-14 · Git tag: `step-20`

## Đã làm
- `Dockerfile` (multi-stage: build React → Python slim, user thường, healthcheck), `.dockerignore`, `docker-compose.yml` (PostgreSQL 16 + app, chỉ mở cổng trên máy, volume dữ liệu).
- Gói `backend[postgres]` (psycopg); bộ test chạy được trên PostgreSQL bằng `TEST_DATABASE_URL`.
- Telegram **webhook** cho production: `POST /api/telegram/webhook`, kiểm tra header secret bằng `hmac.compare_digest`; bắt buộc HTTPS + secret ≥ 16 ký tự.
- CI 4 job: backend (SQLite) · backend-postgres (service PostgreSQL thật) · frontend (tsc + build) · docker build.
- CLI `tools --write` sinh `docs/04-tool-catalog.md` từ registry + policy (test bắt lệch tài liệu); `backup` (SQLite backup API).
- Tài liệu: `02-architecture`, `05-security-governance`, `06-eval-plan`, `07-runbook`, `playbook`; README hoàn chỉnh. Tổng 181 test.

## Khái niệm cần nắm
1. **Một ảnh, một tiến trình** cho app một người dùng: web + bot + job dùng chung EventBus (SSE hoạt động).
2. **Test trên DB thật trong CI**: SQLite và PostgreSQL khác nhau (kiểu dữ liệu, khoá, SQL) — chạy cả hai.
3. **Tài liệu sinh từ code** (tool catalog) + test kiểm tra lệch → tài liệu không bao giờ cũ.
4. **Bảo mật mặc định khi triển khai**: user thường trong container, cổng chỉ mở localhost, HTTPS + cookie secure, webhook có secret.
5. **Runbook** viết trước sự cố: quota 429, 503, bot im lặng, DB khoá, kill switch, sao lưu, xoay vòng bí mật.

## Câu hỏi tự kiểm tra
1. Vì sao webhook Telegram phải kiểm tra header secret?
2. Vì sao compose chỉ mở `127.0.0.1:8000` chứ không `0.0.0.0:8000`?

## Bài tập
`docker compose up -d --build` với `.env` của bạn, mở http://localhost:8000, nhắn Telegram và xem trang Agent Runs.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
