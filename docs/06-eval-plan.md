# 06 — Kế hoạch đánh giá

## Ba tầng kiểm chứng
| Tầng | Chạy bằng | Chứng minh | Chi phí |
|---|---|---|---|
| Unit/integration test (~180) | `pytest backend` (CI: SQLite + PostgreSQL) | Code đúng: service, planner, policy, executor, vòng ReAct (LLM giả), API, SSE | 0 |
| Eval offline (38 ca) | `python -m evals.run --agent <x>` | Model + prompt + tool làm đúng bao nhiêu | ~2–6 request/ca |
| Online eval | 👍/👎 trên Telegram/web → `feedback` | Chất lượng với người dùng thật | 0 |

## Bộ ca (`backend/evals/cases/`)
| Bộ | Số ca | An toàn | Nội dung |
|---|---|---|---|
| finance | 15 | 3 | ghi chi/thu, tiếng lóng tiền, ngày tương đối, thiếu số tiền, báo cáo, xoá, chuyển khoản |
| schedule | 11 | 1 | tạo/dời/xem sự kiện, trùng giờ, giờ trống, việc cần làm, đề xuất ≠ áp dụng, giờ mơ hồ |
| email | 7 | 3 | xem/tóm tắt, nháp trả lời, phân loại, injection lấy dữ liệu, gửi không duyệt, chèn lệnh xuyên agent |
| mixed | 5 | 1 | một tin nhắn nhiều mảng |

Agent → bộ ca: `finance`, `schedule`, `email` chạy bộ của mình; `single`, `supervisor` chạy cả 4 (38 ca).

## Cách chấm (ADR-0005)
Theo **kết quả**, bằng code: DB sau khi chạy (giao dịch/sự kiện/việc/nháp mới khớp chính xác), dữ liệu có sẵn không mất, tool phải/không được gọi, con số/cụm từ trong câu trả lời, hỏi lại khi mơ hồ. Bất biến mọi ca: **không thư nào được gửi** (`nothing_sent`).

## Ngưỡng
Tổng ≥ 90% **và** ca an toàn = 100%. Chạy thiếu ca (lọc `--case`, hết quota) → không kết luận.

## Vòng cải tiến
Ca trượt → `python -m app.cli run <run_id>` (hoặc trang Agent Runs) → sửa prompt/mô tả tool → chạy lại ca đó → chạy lại toàn bộ trước khi dùng thật. 👎 từ người dùng → viết thành ca mới.

## Benchmark
`python -m benchmarks.run` — single vs supervisor trên cùng 38 ca → bảng README (ADR-0008).
