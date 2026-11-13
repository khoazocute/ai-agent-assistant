# Playbook — áp dụng cho dự án agent khác

Rút ra sau 20 bước xây trợ lý multi-agent. Thư mục `backend/app/harness/` không phụ thuộc nghiệp vụ → copy sang dự án mới được ngay.

## 1. Trình tự xây (đừng đảo)
1. **Có cần agent không?** Đường đi cố định → workflow (ADR-0014). Đường đi phụ thuộc yêu cầu → agent.
2. **Gọi LLM tay với 1 tool** trước khi dùng bất kỳ khung nào — hiểu tool use, history, token.
3. **Vòng ReAct tự viết + tracer** ngay từ đầu (ADR-0003): không thấy trace thì không debug được.
4. **Tool là hợp đồng**: schema từ type hint, validate phía mình, risk level, lỗi là Observation.
5. **Service trước, tool sau** (ADR-0004): tool mỏng; con số do code tính.
6. **Eval trước khi chỉnh prompt** (ADR-0005): chấm theo kết quả bằng code, ngưỡng riêng cho an toàn.
7. **Trace vào DB + chi phí** trước khi tối ưu (ADR-0006).
8. **Single-agent trước, multi-agent khi có số liệu** (ADR-0008).
9. **An toàn bằng code**: policy-as-code + duyệt + audit (ADR-0010), dữ liệu ngoài là không tin cậy (ADR-0009).
10. Kênh (Telegram/web) **sau cùng**, mỏng, dùng chung một `Runtime`.

## 2. Checklist 7 harness cho agent mới
- [ ] **Context**: `prompt.md` giải thích *vì sao*; thời điểm hiện tại trong user message; memory có trần.
- [ ] **Tool**: docstring nói *khi nào dùng*; `Literal`/`Field` cho mọi ràng buộc; risk đúng mức; `describe` cho tool cần duyệt.
- [ ] **Orchestration**: `max_steps`; timeout + retry chỉ cho lỗi tạm thời; độ sâu ủy quyền = 1.
- [ ] **Evaluation**: ≥ 10 ca/agent, ≥ 2 ca an toàn, ca mơ hồ (phải hỏi lại), ca liên miền.
- [ ] **Security**: bọc mọi nội dung bên ngoài; agent đọc dữ liệu lạ không có tool hành động nguy hiểm.
- [ ] **Governance**: thêm tool vào `policies.yaml` nếu khác mặc định; audit mọi ghi/xoá/gửi; kill switch thử được.
- [ ] **AgentOps**: run có `agent`, `prompt_version`, `channel`; giá model trong `pricing.yaml`; retention.

## 3. Bài học từ lỗi thật trong dự án
| Lỗi | Bài học |
|---|---|
| Model đoán `amount_vnd=0` khi thiếu số tiền (eval bắt được) | Lớp schema đã chặn, nhưng chỉ eval mới cho biết model *có ý định sai* |
| `cli chat` gọi sai chữ ký hàm lọt qua 4 bước | Test cả lớp kênh (điều phối lệnh), không chỉ lõi |
| Audit mở phiên DB thứ hai → SQLite treo khi chạy thật | Test ở môi trường giống thật (DB file, PostgreSQL) ở chỗ quan trọng |
| So `updated_at > synced_at` → đẩy ngược ghi đè lệnh xoá từ Google | Dùng tín hiệu tường minh thay vì so thời gian |
| faster-whisper 1.2 + PyAV 19 không tương thích | Chạy thử thật một lần mỗi tích hợp; test bản giả không bắt được |
| Quota 20 request/ngày | Thiết kế cho ràng buộc: workflow 1 lượt, eval/benchmark lọc ca, dừng có trật tự khi 429 |

## 4. Số liệu tham khảo (benchmark thử, 2 ca)
Multi-agent: −45% token vào, chậm ~2,8× so với single-agent cùng model. Tách agent vì **an toàn và quyền tối thiểu** nhiều hơn vì chi phí.
