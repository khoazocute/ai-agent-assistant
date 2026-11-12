"""Governance Harness — luật được thực thi bằng code, không chỉ bằng prompt.

- policy_engine.py   đọc config/policies.yaml → allow | require_approval | deny (bước 11)
- audit.py           ghi audit_log cho mọi thao tác ghi và quyết định duyệt  (bước 11)
- prompt_release.py  chỉ kích hoạt prompt mới khi eval đạt ngưỡng             (bước 14)
- killswitch.py      bật/tắt agent hoặc tool không cần deploy lại             (bước 14)
"""
