# 07 — Vận hành (runbook)

## Chạy
| Cách | Lệnh | Khi nào |
|---|---|---|
| Dev (một tiến trình) | `cd backend; uvicorn app.main:app --reload` + `.env` `TELEGRAM_MODE=polling` | Máy cá nhân |
| Sửa giao diện | `cd frontend; npm run dev` (proxy `/api` → :8000) | Phát triển web |
| Bot riêng | `python -m app.integrations.telegram_bot` | Chỉ cần Telegram, không cần web |
| Docker + PostgreSQL | `docker compose up -d --build` | Chạy lâu dài / máy chủ |

Production có domain: đặt sau reverse proxy HTTPS (Caddy/nginx), `.env`: `COOKIE_SECURE=true`, `TELEGRAM_MODE=webhook`, `PUBLIC_BASE_URL=https://…`, `TELEGRAM_WEBHOOK_SECRET=<≥16 ký tự ngẫu nhiên>`.

## Biến môi trường chính
`GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL`, `WEB_PASSWORD`, `JWT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`, `TELEGRAM_MODE`, `FERNET_KEY`, `DEFAULT_AGENT`, `WHISPER_MODEL`, `JOBS_ENABLED`. Mẫu: `.env.example`.

## Kiểm tra sức khoẻ
- `GET /health` (sống), `GET /ready` (DB kết nối được).
- `python -m app.cli stats` — thành công, p50/p95, token, chi phí theo agent.
- `python -m app.cli runs` / `run <id>` — xem run lỗi; `audit` — ai đã làm gì.

## Sự cố thường gặp
| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| "Hết lượt gọi AI hôm nay" / `429 RESOURCE_EXHAUSTED` | Gói Gemini miễn phí ~20 request/ngày/model | Bật billing ở Google AI Studio, hoặc đổi `GEMINI_MODEL` sang model khác (quota riêng), hoặc chờ reset (~15h giờ VN) |
| Trả lời chậm 30–60s, log `503`/`504` | Gemini quá tải | Tự retry (5 lần, backoff); nếu kéo dài, đổi model |
| Bot không trả lời | Sai token / chat_id chưa trong allowlist / chạy 2 bot cùng token | Nhắn `/start` xem chat_id; chỉ chạy MỘT tiến trình polling |
| "Chưa kết nối Google" | Chưa OAuth / token hết hạn bị thu hồi | `python -m app.integrations.google_auth` |
| `database is locked` | Nhiều tiến trình ghi SQLite | Dùng một tiến trình (web + bot + job), hoặc PostgreSQL |
| Web không tự cập nhật khi nhắn Telegram | Bot chạy tiến trình riêng | `TELEGRAM_MODE=polling` để bot chạy trong tiến trình web |
| Cần dừng một agent ngay | Agent hành xử sai | `config/policies.yaml` → `disabled_agents: [email]` (hiệu lực ngay) |

## Đổi prompt an toàn
1. Sửa `backend/app/agents/<agent>/prompt.md` (version = hash → tự đổi).
2. `python -m evals.run --agent <agent> --delay 5` → phải đạt ≥ 90% và an toàn 100%.
3. Trượt → đọc trace ca trượt → sửa → lặp. Quay lại bản cũ: `git checkout <commit> -- backend/app/agents/<agent>/prompt.md`.

## Sao lưu / khôi phục
- SQLite: `python -m app.cli backup` → `backend/data/backups/app-<thời điểm>.db`. Khôi phục: dừng app, chép file về `backend/data/app.db`.
- PostgreSQL: `docker compose exec db pg_dump -U assistant assistant > backup.sql`; khôi phục `psql -U assistant assistant < backup.sql`.

## Xoay vòng bí mật
Gemini key / Telegram token / JWT_SECRET (đăng xuất mọi phiên) / FERNET_KEY (phải đăng nhập Google lại) → sửa `.env` → khởi động lại.
