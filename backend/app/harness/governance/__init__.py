"""Governance Harness — luật lệ, trách nhiệm giải trình, khả năng tắt khẩn cấp.

- policy_engine.py  policy-as-code từ config/policies.yaml: allow / require_approval / deny,
                    kill switch theo tool/agent, luật cứng "external luôn cần duyệt"   (bước 11, ADR-0010)
- audit.py          audit_log: ai đã làm gì, lúc nào — chỉ ghi thêm                    (bước 11)
- prompt_release    kích hoạt prompt khi eval đạt ngưỡng — xem evals/ + ADR-0005
"""
