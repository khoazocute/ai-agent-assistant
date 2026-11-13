# Bước 13 — Website (FastAPI + React)
- Ngày: 2026-11-14 · Git tag: `step-13`

## Đã làm
- Backend `app/main.py` + `app/api/`: auth (cookie httpOnly, giới hạn đăng nhập sai), finance, schedule, email, approvals, agentops (runs, metrics, audit, policy), chat; lỗi nghiệp vụ → 400; `/health`, `/ready`; phục vụ `frontend/dist` cùng domain.
- `harness/security/auth.py`: so mật khẩu thời gian hằng, JWT, rate limit.
- Frontend `frontend/` (Vite + React + TS + TanStack Query + FullCalendar + Recharts): Đăng nhập, Tổng quan, Chat (kèm duyệt + 👍/👎 + link trace), Chi tiêu (biểu đồ, thêm/xoá), Lịch (kéo chọn tạo, kéo thả dời, việc cần làm, đề xuất → áp dụng), Email & Duyệt.
- Sửa lỗi thật: audit mở phiên DB thứ hai → SQLite treo khi chạy thật; nay audit ghi cùng transaction + WAL + busy_timeout; test API dùng DB file.

## Khái niệm cần nắm
1. **Cùng domain** cho API và giao diện → không CORS, cookie an toàn hoạt động.
2. **Cookie httpOnly** → JavaScript (kể cả mã độc XSS) không đọc được phiên.
3. **Router mỏng → service chung** → web, CLI, agent ra cùng con số.
4. **Test phải giống môi trường thật ở chỗ quan trọng**: DB trong RAM che mất lỗi tranh khoá.

## Câu hỏi tự kiểm tra
1. Vì sao người dùng xoá trên web không cần duyệt, còn agent xoá thì cần?
2. Vì sao endpoint `/api/chat` đẩy agent sang threadpool?

## Bài tập
README → "Chạy website": đặt `WEB_PASSWORD`, `JWT_SECRET`, `npm run build`, `uvicorn app.main:app`, mở http://localhost:8000.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
