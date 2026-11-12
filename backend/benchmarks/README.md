# benchmarks/ — single-agent vs multi-agent
- `cases/*.yaml` — ~40 ca, 4 nhóm: đơn giản · nhiều bước · liên miền · an toàn
- `run.py` — `python -m benchmarks.run --arch single,multi --effort low,medium --repeats 3`
  (ước tính chi phí và hỏi xác nhận trước khi chạy)
- `report.py` — sinh bảng markdown, tự chèn vào README giữa `<!-- BENCH:START -->` và `<!-- BENCH:END -->`
- `results/<ngày>.json` — kết quả tổng hợp

Lần 1: bước 9. Đầy đủ: bước 19. Số liệu **không bao giờ điền tay**.
