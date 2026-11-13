# ADR-0006: Tự lưu trace vào DB (không dùng Langfuse/LangSmith lúc này)
- Trạng thái: Accepted
- Ngày: 2026-11-13
- Bước: 6

## Bối cảnh
File JSONL (bước 2) đủ để đọc một run, nhưng không trả lời được: agent nào lỗi nhiều nhất? p95 độ trễ? tốn bao nhiêu tiền/ngày? Website (bước 13–14) cũng cần đọc trace để hiển thị trang Agent Runs.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Langfuse / LangSmith (SaaS hoặc tự host) | UI đẹp sẵn, nhiều tính năng | Gửi prompt + dữ liệu cá nhân (chi tiêu, email) ra dịch vụ ngoài; thêm hạ tầng; che mất cơ chế |
| B. Tự lưu vào DB của app: `agent_runs` (tổng hợp) + `agent_events` (JSON nguyên văn) | Dữ liệu ở lại máy mình; truy vấn SQL; web đọc trực tiếp | Tự viết UI và thống kê |
| C. Chỉ JSONL + script phân tích | Đơn giản nhất | Không truy vấn được, web khó đọc |

## Quyết định
Chọn **B**. Tracer gửi mỗi sự kiện tới nhiều *sink* (JSONL, console, DB; bước 14 thêm SSE). Bảng nằm trong `HarnessBase` riêng (không import nghiệp vụ). Chi phí tính từ `config/pricing.yaml`; model chưa có giá → `None` (không đoán). CLI: `runs`, `run <id>`, `stats`.

## Hệ quả
- Được: trả lời được "agent đã đọc prompt nào, gọi tool nào" bằng một lệnh; số liệu p50/p95/chi phí cho benchmark; dữ liệu riêng tư không rời máy.
- Mất: `agent_events` lưu cả history mỗi bước → DB lớn dần; cần job dọn trace > 90 ngày (bước 16, đúng chính sách lưu trữ trong PLAN).
- Xem lại khi: cần so sánh trace giữa nhiều dự án/nhóm → xuất OpenTelemetry sang Langfuse (sink mới, không đổi vòng ReAct).
