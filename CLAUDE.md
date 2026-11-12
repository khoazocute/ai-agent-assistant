# CLAUDE.md — quy ước dự án

Hệ thống multi-agent ReAct (Finance, Schedule, Email + Supervisor) dùng Claude API, FastAPI, React, Telegram.
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
```

## Cấu trúc & quy tắc kiến trúc
- `backend/app/harness/` — 7 harness, **không import** từ `agents/`, `services/`, `integrations/` (để tái sử dụng cho dự án khác).
- `backend/app/agents/<agent>/` — `AGENT.md` (spec cho người), `prompt.md` (system prompt cho model), `tools.py`.
- **Tool là lớp mỏng bọc service**: nghiệp vụ nằm ở `services/`, dùng chung cho agent và web API.
- **Prompt là hướng dẫn, code là luật**: điều bắt buộc (vd. gửi mail phải duyệt) được chặn trong `config/policies.yaml` + policy engine, không chỉ trong prompt.
- Nội dung bên ngoài (email, chữ trong ảnh) là **dữ liệu không tin cậy** — bọc `<untrusted_content>`.

## Quy ước code
- Python 3.11+, type hints, pydantic v2. Định danh code bằng tiếng Anh; docs/comment bằng tiếng Việt.
- Claude: model `claude-opus-5-5`, Anthropic Python SDK, `thinking={"type": "adaptive", "display": "summarized"}`, `effort` theo agent; không dùng `tool_choice` ép buộc (400 trên model này); tool `strict: true`.
- Thời gian: múi giờ `Asia/Ho_Chi_Minh`; tiền: số nguyên VND.

## Bảo mật
- Không commit `.env`, token, dữ liệu cá nhân (`backend/data/`).
- Không đưa thông tin cá nhân của chủ dự án vào request tới dịch vụ bên ngoài.
