# benchmarks/ — single-agent vs multi-agent
Chạy **cùng bộ ca eval** (`evals/cases/finance|schedule|mixed.yaml`, 31 ca, 5 ca an toàn) cho hai cấu hình và so sánh.

```powershell
cd backend
python -m benchmarks.run --delay 5                        # single + supervisor (~150 request — cần billing hoặc chia nhiều ngày)
python -m benchmarks.run --agents single --suite mixed    # một phần
python -m benchmarks.report                               # dựng lại bảng README từ kết quả mới nhất
```
- `run.py` — chạy, tóm tắt: đạt (tổng/an toàn/từng bộ), p50/p95, token vào/ra, bước, chi phí/ca
- `report.py` — sinh bảng markdown, tự chèn vào README giữa `<!-- BENCH:START -->` và `<!-- BENCH:END -->`
- `results/<thời điểm>.json` — kết quả tóm tắt (commit — là bằng chứng cho ADR-0008)

Token/chi phí của multi-agent = Supervisor **+ mọi sub-agent** (tính đủ để so sánh công bằng).
Số liệu **không bao giờ điền tay**.
