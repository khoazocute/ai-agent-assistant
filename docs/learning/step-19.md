# Bước 19 — Benchmark single vs multi-agent
- Ngày: 2026-11-14 · Git tag: `step-19`

## Đã làm
- `benchmarks/run.py` thêm `--case` (chạy ca chọn lọc khi quota ít); báo cáo ghi rõ "số liệu minh hoạ, chưa đủ kết luận".
- Chạy thật trên `gemini-3.5-flash-lite` (quota riêng — giữ quota model chính cho người dùng) với 2 ca phân biệt rõ nhất: `mix-001` (liên miền) và `eml-007` (email chèn lệnh xuyên agent).
- Bảng README mục 5 sinh tự động; ADR-0008 cập nhật bằng chứng (vẫn Proposed).

## Kết quả thật
| | Single | Supervisor |
|---|---|---|
| Đạt | 2/2 | 2/2 |
| Token vào/ca | 17.184 | 9.480 |
| p50 | 3,1s | 8,6s |

## Khái niệm cần nắm
1. **Multi-agent không "tốt hơn" mặc định**: rẻ hơn về token vào (prompt ngắn), nhưng chậm hơn (lượt gọi nối tiếp) và nhiều token ra hơn.
2. **Chọn ca benchmark có chủ đích** khi tài nguyên giới hạn: ca phân biệt được hai cấu hình đáng giá hơn ca dễ.
3. **Trung thực với số liệu**: 2 ca → "minh hoạ", không phải "kết luận"; ADR giữ Proposed.
4. **Cố định mọi biến trừ biến cần so** (cùng model, cùng ca, cùng "bây giờ").

## Câu hỏi tự kiểm tra
1. Vì sao single-agent tốn nhiều token vào hơn dù ít lượt gọi hơn?
2. Nếu người dùng chủ yếu dùng Telegram trên điện thoại, độ trễ hay chi phí quan trọng hơn?

## Bài tập
Khi bật billing: `python -m benchmarks.run --delay 2` (38 ca × 2 cấu hình) rồi cập nhật ADR-0008 thành Accepted.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
