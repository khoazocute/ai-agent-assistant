# evals/ — bộ đánh giá agent
Viết eval **trước** khi tinh chỉnh prompt (bước 5).

- `cases/<agent>.yaml` — câu tiếng Việt → tool mong đợi, tham số mong đợi, trạng thái DB mong đợi
- `media/` — ảnh hóa đơn và đoạn thu âm mẫu (bước 17–18)
- `run.py` — `python -m evals.run --agent finance`; mỗi ca chạy trên DB tạm, kết quả lưu theo prompt version

Ngưỡng release prompt: tổng ≥ 90%, ca an toàn 100%.
