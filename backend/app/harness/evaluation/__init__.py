"""Evaluation Harness — đo chất lượng agent bằng số liệu, không bằng cảm giác.

- scorer.py    chấm: đúng tool, đúng tham số, an toàn, trạng thái DB   (bước 5)
- feedback.py  phản hồi tốt/chưa đúng từ Telegram → ca eval mới       (bước 12)
Bộ ca kiểm thử nằm ở backend/evals/, benchmark ở backend/benchmarks/.
"""
