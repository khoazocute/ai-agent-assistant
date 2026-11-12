# ADR-0001: Ghi lại quyết định kiến trúc bằng ADR
- Trạng thái: Accepted
- Ngày: 2026-11-12
- Bước: 0

## Bối cảnh
Dự án được xây dần qua 20 bước để vừa làm vừa học, và sẽ được dùng làm mẫu cho các dự án agent sau. Nhiều quyết định có đánh đổi rõ ràng (tự viết vòng ReAct hay dùng framework, single hay multi-agent, SSE hay WebSocket…). Nếu chỉ nằm trong code hoặc lịch sử chat, lý do sẽ bị quên — kể cả với chính người viết sau vài tháng.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Không ghi, đọc code là hiểu | Không tốn công | Code cho biết *cái gì*, không cho biết *vì sao* và *đã cân nhắc gì* |
| B. Một file thiết kế lớn, sửa liên tục | Tập trung một chỗ | Mất lịch sử: không biết trước đây quyết định gì và vì sao đổi |
| C. ADR: mỗi quyết định một file ngắn, đánh số, bất biến | Có lịch sử, dễ đọc, dễ link từ README | Phải giữ kỷ luật viết đúng lúc |

## Quyết định
Chọn **C**. Mỗi quyết định kiến trúc có một file `docs/adr/NNNN-<slug>.md` theo mẫu `0000-template.md`, viết **ngay tại bước đưa ra quyết định**. ADR đã Accepted không sửa nội dung; nếu đổi ý, viết ADR mới và đánh dấu ADR cũ là *Superseded*.

## Hệ quả
- Được: README có mục lục quyết định; người đọc (và chính mình sau này) hiểu lý do; dễ tái sử dụng sang dự án khác qua `docs/playbook.md`.
- Mất: mỗi quyết định tốn thêm ~15 phút viết.
- Xem lại khi: số ADR quá nhiều khiến khó tra cứu → thêm phân loại trong `docs/adr/README.md`.

## Bằng chứng
- Michael Nygard, “Documenting Architecture Decisions” (2011) — nguồn gốc định dạng ADR.
- MADR (Markdown Any Decision Records) — mẫu rút gọn được dùng ở đây.
