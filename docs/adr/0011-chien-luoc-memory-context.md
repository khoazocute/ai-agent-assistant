# ADR-0011: Chiến lược memory & context
- Trạng thái: Accepted
- Ngày: 2026-11-14
- Bước: 12

## Bối cảnh
Trên Telegram người dùng nhắn nối tiếp: "chiều mai 3h họp nhóm" → "à dời nó sang 4h". Agent cần nhớ ngữ cảnh. Nhưng mỗi lượt gọi LLM gửi lại toàn bộ lịch sử (bước 1–2) → càng nhớ nhiều càng tốn token, và nội dung email không tin cậy có thể "bám" lại trong lịch sử.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Không nhớ (mỗi tin một run độc lập) | Rẻ, đơn giản | "dời nó sang 4h" không hiểu được |
| B. Gửi lại toàn bộ lịch sử, gồm cả tool call/kết quả | Đầy đủ nhất | Token tăng không giới hạn; kéo theo nội dung email cũ (rủi ro injection) |
| C. N lượt gần nhất, **chỉ chữ** (người dùng + câu trả lời cuối), có hạn tuổi | Đủ hiểu đại từ/nối tiếp; chi phí trần cố định | Mất chi tiết tool cũ (vd. id giao dịch) — agent phải tra lại |
| D. Tóm tắt lịch sử bằng LLM | Nhớ lâu | Thêm một lượt gọi LLM mỗi lần; tóm tắt có thể sai |

**Memory dài hạn**: tự động nhét mọi "sự thật" vào prompt, hay để agent tra khi cần?

## Quyết định
- Ngắn hạn: **C** — 6 lượt gần nhất trong 12 giờ, theo từng cuộc trò chuyện (`channel` + `external_id`), lệnh `/reset` để xoá.
- Dài hạn: bảng `user_facts`, tool `remember_fact` (chỉ khi người dùng **chủ động** nhờ nhớ) và `recall_facts` (agent tra khi cần) — không tự nhét vào mọi prompt.
- Thời điểm hiện tại vẫn đặt trong user message (prompt hệ thống cố định → version ổn định).
- `ChatService` (không phụ thuộc kênh) gom: memory → agent → lưu lượt → yêu cầu duyệt mới.

## Hệ quả
- Chi phí mỗi tin có trần (≤ 6 lượt chữ + prompt + tool).
- Agent có thể phải gọi lại `list_events` để lấy id cho "dời nó" — chấp nhận (an toàn hơn dùng id cũ).
- Xem lại khi: người dùng cần nhớ chủ đề dài nhiều ngày → thêm tóm tắt (D) cho phần cũ.
