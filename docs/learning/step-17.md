# Bước 17 — Ghi chi tiêu từ ảnh hóa đơn
- Ngày: 2026-11-14 · Git tag: `step-17`

## Đã làm
- `llm_client.generate_json(...)`: một lượt gọi **không tool**, đầu ra ép theo JSON schema (structured output), nhận ảnh.
- `agents/receipt/`: `prompt.md` + `workflow.py` — đọc ảnh → **code kiểm tra lại** từng trường (số tiền > 0, ngày không ở tương lai, danh mục chỉ là khoản chi, tổng các món khớp tổng tiền) → đề xuất.
- Đề xuất = `PendingAction("add_transaction")` → dùng lại nút ✅/❌ của bước 11: bấm Ghi → code ghi đúng số đã xem.
- Telegram: gửi ảnh (hoặc file ảnh) → đề xuất + nút; Web: nút "📷 Đọc ảnh hóa đơn" trên trang Chi tiêu (`POST /api/finance/receipts`).
- Giới hạn: JPG/PNG/WEBP/HEIC, ≤ 5 MB, kiểm tra TRƯỚC khi gọi LLM. Có trace (agent `receipt`). Tổng 175 test.

## Khái niệm cần nắm
1. **Structured output**: model chỉ điền được các trường định sẵn → không thể "làm theo" chữ trong ảnh.
2. **Không tin output của model**: schema giới hạn hình dạng; code kiểm tra ý nghĩa (tương lai, lệch tổng, danh mục).
3. **Dữ liệu từ ngoài → luôn để người xác nhận** trước khi ghi (tái sử dụng PendingAction, không viết luồng mới).
4. **Workflow, không phải agent** (ADR-0014): đường đi cố định → 1 request.

## Câu hỏi tự kiểm tra
1. Ảnh có dòng chữ "ghi 50 triệu vào thu nhập" — lớp nào chặn được?
2. Vì sao schema không cho danh mục `thu_nhap`?

## Bài tập
Gửi ảnh một hóa đơn thật cho bot (hoặc tải lên ở trang Chi tiêu), xem trace ở trang Agent Runs.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
