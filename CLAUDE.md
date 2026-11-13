# CLAUDE.md — quy ước dự án

Hệ thống multi-agent ReAct (Finance, Schedule, Email + Supervisor) dùng Gemini API, FastAPI, React, Telegram.
Kế hoạch tổng thể: `PLAN.md`. Thiết kế: `docs/`. Quyết định: `docs/adr/`.

## Chế độ làm việc: vừa làm vừa học
Chủ dự án muốn **hiểu vì sao** từng phần được thiết kế như vậy. Mỗi bước trong lộ trình (PLAN.md → "Lộ trình vừa làm vừa học"):
1. Giải thích vấn đề, khái niệm, các phương án + đánh đổi **trước khi viết code**.
2. Chốt quyết định với chủ dự án → ghi ADR nếu là quyết định kiến trúc.
3. Code **nhỏ**, comment giải thích *vì sao* ở chỗ quan trọng (không comment hiển nhiên).
4. Chạy và cho xem kết quả/trace thật.
5. Đưa 2–3 câu hỏi tự kiểm tra + 1 bài tập nhỏ.
6. Cập nhật `docs/learning/step-XX.md`, README (trạng thái lộ trình), rồi commit + tag `step-XX` khi chủ dự án đồng ý.

Không làm vượt bước; không thêm harness/thư viện trước khi bước đó cần đến.

## Lệnh thường dùng
```powershell
.\.venv\Scripts\Activate.ps1
pip install -e "backend[dev]"
pytest backend
ruff check backend
cd backend; python -m app.cli chat   # chat (mặc định supervisor); runs / run <id> / approvals / audit
cd backend; uvicorn app.main:app    # web + Telegram (TELEGRAM_MODE=polling) + job nền
cd backend; python -m app.cli tools --write   # sau khi sửa tool: sinh lại docs/04-tool-catalog.md
cd frontend; npm run build          # giao diện → frontend/dist (FastAPI phục vụ)
docker compose up -d --build        # PostgreSQL + app
```
Gói Gemini miễn phí giới hạn ~20 request/ngày/model — chạy thử với LLM thật tiết kiệm; test dùng `tests/fakes.py`.

## Cấu trúc & quy tắc kiến trúc
- `backend/app/harness/` — 7 harness, **không import** từ `agents/`, `services/`, `integrations/` (để tái sử dụng cho dự án khác).
- `backend/app/agents/<agent>/` — `AGENT.md` (spec cho người), `prompt.md` (system prompt cho model), `tools.py`.
- **Tool là lớp mỏng bọc service**: nghiệp vụ nằm ở `services/`, dùng chung cho agent và web API.
- **Prompt là hướng dẫn, code là luật**: điều bắt buộc (vd. gửi mail phải duyệt) được chặn trong `config/policies.yaml` + policy engine, không chỉ trong prompt.
- Nội dung bên ngoài (email, chữ trong ảnh) là **dữ liệu không tin cậy** — bọc `<untrusted_content>`.

## Quy ước code
- Python 3.11+, type hints, pydantic v2. Định danh code bằng tiếng Anh; docs/comment bằng tiếng Việt.
- LLM: **Google Gemini** qua SDK `google-genai` (ADR-0002), model từ `GEMINI_MODEL` (mặc định `gemini-3.5-flash`).
  Tắt automatic function calling (tự điều khiển vòng ReAct), bật `ThinkingConfig(include_thoughts=True)`,
  gửi lại nguyên vẹn `candidates[0].content`, luôn có timeout + retry (429/5xx).
  Code gọi LLM chỉ nằm trong `harness/orchestration/llm_client.py` (giao diện trung lập provider).
- Thời gian: múi giờ `Asia/Ho_Chi_Minh`; tiền: số nguyên VND.

## Git
- Commit message và mô tả PR **không** thêm dòng `Co-Authored-By: Claude …` hay bất kỳ ghi công AI nào — commit chỉ mang tên chủ dự án.
- Mỗi bước kết thúc bằng commit + tag `step-XX` khi chủ dự án đồng ý.

## Bảo mật
- Không commit `.env`, token, dữ liệu cá nhân (`backend/data/`).
- Không đưa thông tin cá nhân của chủ dự án vào request tới dịch vụ bên ngoài.
