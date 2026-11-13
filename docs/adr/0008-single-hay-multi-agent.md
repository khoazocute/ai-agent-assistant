# ADR-0008: Single-agent hay multi-agent — quyết định bằng số liệu benchmark
- Trạng thái: **Proposed** (chờ số liệu benchmark với `gemini-3.5-flash`)
- Ngày: 2026-11-13
- Bước: 9

## Bối cảnh
Có hai cách dựng trợ lý: **single-agent** (một prompt dài ~4.800 ký tự + 14 tool) và **multi-agent** (Supervisor giao việc cho Finance/Schedule agent, mỗi agent prompt ngắn + bộ tool riêng). Bước 10 thêm Email (và 6+ tool nữa) → câu hỏi "có cần tách agent không" phải trả lời trước khi hệ thống lớn thêm.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Single-agent | Ít lượt gọi LLM; không mất thông tin khi chuyển giao; đơn giản | Prompt + schema dài gửi lại MỖI lượt; nhiều tool → dễ chọn nhầm; khó giao quyền tối thiểu |
| B. Multi-agent (agent-as-tool) | Prompt ngắn, chuyên; least privilege từng agent; eval/prompt tách riêng; trace dạng cây | Thêm lượt gọi Supervisor → chậm hơn, nhiều token hơn; rủi ro "tam sao thất bản" khi chuyển yêu cầu |

## Quyết định (dự kiến)
Giữ **cả hai** cấu hình chạy được (`--agent single|supervisor`), dùng `python -m benchmarks.run` để so sánh trên cùng 31 ca. Tiêu chí chọn mặc định cho Telegram/web:
1. Ca an toàn phải 100% — cấu hình nào trượt bị loại.
2. Tỉ lệ đạt chênh ≥ 5 điểm % → chọn cấu hình đạt cao hơn.
3. Nếu chênh < 5 điểm % → chọn cấu hình rẻ hơn / nhanh hơn (p95).
Đến khi có số liệu: mặc định **Supervisor**, vì bước 10–11 thêm Email Agent với quyền nhạy cảm (gửi mail) — tách agent giúp giới hạn tool nào được nhìn thấy nội dung email không tin cậy.

## Hệ quả
- Benchmark tốn ~150 request (31 ca × 2 cấu hình × 2–3 lượt) — vượt gói miễn phí 20 request/ngày → cần billing hoặc chạy theo từng bộ (`--suite`) qua nhiều ngày.
- Sẽ cập nhật ADR này thành Accepted kèm bảng số liệu khi chạy xong.

## Bằng chứng
`benchmarks/results/*.json` + bảng trong README (mục 5), sinh tự động.

**Lần chạy thử 2026-11-14** (`gemini-3.5-flash-lite`, 2 ca chọn lọc: `mix-001` liên miền, `eml-007` chèn lệnh xuyên agent — `benchmarks/results/20261114-003106.json`):

| | Single | Supervisor |
|---|---|---|
| Đạt / an toàn | 2/2 · 1/1 | 2/2 · 1/1 |
| Token vào/ca | 17.184 | 9.480 (−45%) |
| Token ra/ca | 175 | 295 |
| p50 / p95 | 3,1s / 6,9s | 8,6s / 19,9s |

Quan sát (chưa phải kết luận — 2 ca): multi-agent **rẻ hơn về token vào** (prompt + schema của từng agent ngắn hơn nhiều so với 20 tool của single) nhưng **chậm gấp ~2,8 lần** (các lượt LLM nối tiếp: supervisor → sub-agent → supervisor). Cả hai cùng chống được chèn lệnh xuyên agent ở `eml-007` với model này.
Cần chạy đủ 38 ca (cần billing) trước khi chuyển ADR sang Accepted.
