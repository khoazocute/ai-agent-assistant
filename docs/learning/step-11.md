# Bước 11 — Duyệt (human-in-the-loop), policy-as-code, audit
- Ngày: 2026-11-13 · Git tag: `step-11`

## Đã làm
- `config/policies.yaml` + `harness/governance/policy_engine.py` (allow / require_approval / deny, kill switch, hot reload, luật cứng external).
- `harness/orchestration/approvals.py`: `PendingAction`, `ApprovalStore` (create / approve → thực thi đúng tham số / reject / expire).
- `harness/governance/audit.py`: `audit_log`.
- `ToolExecutor`: validate → policy → chạy | tạo yêu cầu duyệt | từ chối → audit. Tool rủi ro có `describe` cho người duyệt.
- `app/runtime.py`: dựng mọi thứ dùng chung; CLI: `approvals`, `approve <id>`, `reject <id>`, `audit`; `chat` có memory trong phiên.
- Sửa lỗi: `cli chat` gọi sai chữ ký hàm (lọt từ bước 7) + test điều phối lệnh CLI để không lặp lại. Tổng 125 test.

## Khái niệm cần nắm
1. **Duyệt cái sẽ xảy ra, và chỉ cái đó xảy ra**: PendingAction lưu tham số đã kiểm tra; duyệt → code chạy đúng tham số, không hỏi lại LLM.
2. **Policy là dữ liệu, engine là code**: đổi luật = sửa YAML; nhưng luật sống còn (external luôn duyệt) nằm trong code để YAML sai cũng không phá được.
3. **Kill switch**: tắt một agent/tool trong vài giây, không cần deploy.
4. **Idempotency khi duyệt**: bấm hai lần không gửi hai thư; yêu cầu quá hạn không duyệt được.
5. **Trace vs audit**: trace = agent nghĩ gì; audit = điều gì thực sự thay đổi, ai cho phép.

## Câu hỏi tự kiểm tra
1. Vì sao không cho agent tự gửi khi người dùng nhắn "ok gửi đi"?
2. Nếu ai đó sửa `policies.yaml` thành `send_email: allow`, chuyện gì xảy ra? Vì sao?
3. Vì sao executor kiểm tra tham số *trước* khi hỏi policy?

## Bài tập
1. `chat --agent finance`: "xoá khoản ăn phở hôm nay" → `python -m app.cli approvals` → `approve <id>` → `python -m app.cli audit`.
2. Thêm `disabled_agents: [email]` vào `policies.yaml` khi đang chat với supervisor, rồi nhờ "xem thư mới".

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
