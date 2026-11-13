"""Evaluation Harness — đo chất lượng agent bằng số liệu, không bằng cảm giác.

- scorer.py    check dùng chung (tool, con số trong câu trả lời, hỏi lại), CaseResult, EvalSummary,
               ngưỡng tổng ≥ 90% + an toàn 100%, báo cáo                          (bước 5, ADR-0005)
- feedback.py  phản hồi tốt/chưa đúng từ Telegram → ca eval mới                    (bước 12)
Bộ ca + runner nằm ở backend/evals/, benchmark ở backend/benchmarks/.
"""
