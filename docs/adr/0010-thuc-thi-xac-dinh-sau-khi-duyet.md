# ADR-0010: Policy-as-code + duyệt; sau khi duyệt, thực thi xác định — không gọi lại LLM
- Trạng thái: Accepted
- Ngày: 2026-11-13
- Bước: 11

## Bối cảnh
Bước 3–10 chỉ *chặn* tool rủi ro. Người dùng cần *làm được* (gửi thư, xoá giao dịch) nhưng có kiểm soát. Câu hỏi: khi người dùng bấm "Duyệt", hệ thống làm gì?

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Duyệt = nhắn "đồng ý" cho agent, agent gọi lại tool | Tự nhiên | LLM có thể gọi khác đi (đổi người nhận, sửa nội dung) — thứ được duyệt ≠ thứ được làm; prompt injection có thể giả "đồng ý" |
| B. Lưu `PendingAction` (tool + tham số đã kiểm tra); duyệt → **code** chạy đúng tool + tham số đó | Thứ người dùng thấy = thứ xảy ra; không cần LLM; chống bấm hai lần, hết hạn | Cần bảng + giao diện duyệt |

**Luật để ở đâu**: trong prompt (A) hay file policy được code thực thi (B)?

## Quyết định
- **B**. `harness/orchestration/approvals.py`: `pending → approved → executed|failed`, `rejected`, `expired` (TTL 24h). Duyệt lại một yêu cầu đã xử lý → lỗi.
- Executor: validate tham số → **hỏi policy** → allow chạy / require_approval tạo PendingAction (model nhận "đã tạo yêu cầu #id, CHƯA thực hiện") / deny từ chối.
- **Policy-as-code** `config/policies.yaml`: mặc định theo mức rủi ro, luật riêng theo tool, `disabled_tools/agents` (kill switch, đọc lại khi file đổi). **Luật cứng trong code**: risk `external` không bao giờ `allow`, kể cả YAML ghi sai.
- Tool rủi ro có `describe(...)` → người duyệt thấy đúng điều sẽ xảy ra (thư: người nhận + tiêu đề + nội dung + cảnh báo PII).
- **Audit** (`audit_log`): mọi tool ghi/xoá/gửi đã chạy, mọi yêu cầu/duyệt/từ chối.
- `app/runtime.py`: mọi kênh (CLI, Telegram, web) dựng agent với executor có policy + duyệt + audit — không có đường tắt.

## Hệ quả
- Được: gửi thư trở nên khả dụng mà vẫn an toàn; kill switch không cần deploy; truy vết đầy đủ.
- Mất: thêm một bước của người dùng cho mỗi hành động rủi ro (cố ý).
- Lưu ý: kết quả sau khi duyệt không quay lại cuộc hội thoại của agent — kênh (Telegram/web) báo trực tiếp cho người dùng.
