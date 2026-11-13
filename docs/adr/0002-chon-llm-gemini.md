# ADR-0002: Dùng Google Gemini làm LLM, gọi qua SDK chính thức `google-genai`
- Trạng thái: Accepted
- Ngày: 2026-11-13
- Bước: 1

## Bối cảnh
Kế hoạch ban đầu dùng Claude (Anthropic). Khi bắt đầu bước 1, chủ dự án chưa có Anthropic API key nhưng có Gemini API key (Google AI Studio, có gói miễn phí). Mục tiêu của giai đoạn đầu là **học cơ chế agent** — cơ chế tool use / ReAct giống nhau giữa các nhà cung cấp, chỉ khác cú pháp.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Chờ có Claude key | Giữ nguyên kế hoạch | Chặn tiến độ |
| B. Gemini qua SDK `google-genai` | Có key ngay, gói miễn phí, hỗ trợ function calling + tóm tắt suy luận + đọc ảnh | Một số chi tiết khác Claude (xem Hệ quả) |
| C. Gemini qua framework đa nhà cung cấp (LangChain…) | Đổi provider dễ | Che mất cơ chế — trái mục tiêu học (xem ADR-0003 dự kiến) |

## Quyết định
Chọn **B**. Model mặc định `gemini-3.5-flash`, cấu hình qua `GEMINI_MODEL` trong `.env`.
Ở bước 2, `harness/orchestration/llm_client.py` được thiết kế với **giao diện trung lập** (message, tool call, tool result, usage) để sau này có thể thêm Claude hoặc provider khác mà không sửa vòng ReAct — và benchmark giữa các provider.

## Hệ quả
- **Khác biệt đã gặp ở bước 1:**
  - Gemini không có `stop_reason="tool_use"`: cả khi gọi tool lẫn khi trả lời xong đều `finish_reason=STOP` → phải kiểm tra `response.function_calls`.
  - SDK mặc định **tự động chạy hàm Python** (automatic function calling) và giấu vòng lặp → phải tắt (`disable=True`) để tự điều khiển và trace.
  - Phải gửi lại nguyên vẹn `candidates[0].content` (có *thought signature*) ở lượt sau.
  - Tóm tắt suy luận bật bằng `ThinkingConfig(include_thoughts=True)`; bản tóm tắt hiện bằng tiếng Anh.
- **Độ ổn định:** gói miễn phí hay gặp `503 high demand` / `504 deadline` theo đợt; một số model cũ (`gemini-2.5-*`) không mở cho tài khoản mới → **bắt buộc có timeout + retry với backoff** (đã thêm từ bước 1).
- Các phần trong PLAN.md viết riêng cho Claude (effort, server-side fallback, prompt caching) sẽ được thay bằng tương đương của Gemini khi tới bước tương ứng.
- Xem lại khi: có Claude key (thêm provider thứ hai vào `llm_client`), hoặc độ ổn định gói miễn phí ảnh hưởng tới eval/benchmark.

## Bằng chứng
- Trace bước 1: `backend/data/traces/first_tool_call.json` (không commit).
- Đo nhanh ngày 2026-11-13: `gemini-3.5-flash` ~2–3s/lượt khi không quá tải; `gemini-3.8-flash` trả 503; `gemini-2.5-flash/pro` trả 404 cho tài khoản mới.
