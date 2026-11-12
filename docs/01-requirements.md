# 01 — Yêu cầu sản phẩm (PRD)
> Bước 1 của quy trình thiết kế agent: **xác định bài toán và tiêu chí thành công** trước khi viết code.

## 1. Bối cảnh & vấn đề
Công việc cá nhân hằng ngày bị phân mảnh: chi tiêu ghi không đều, lịch và việc cần làm rời rạc, hộp thư quá tải. Các app riêng lẻ đòi hỏi nhập liệu thủ công nên dễ bỏ dở.

**Mục tiêu:** một trợ lý cá nhân nhận lệnh bằng ngôn ngữ tự nhiên qua Telegram (chữ, ảnh, giọng nói), lưu dữ liệu và quản lý trên website, minh bạch về những gì AI đã làm.

## 2. Người dùng
Một người dùng duy nhất (chủ hệ thống). Dùng Telegram trên điện thoại khi di chuyển, website trên máy tính để xem tổng quan, duyệt và chỉnh sửa.

## 3. Có thật sự cần agent không?
| Tiêu chí | Đánh giá |
|---|---|
| Độ phức tạp | Yêu cầu tự nhiên, nhiều dạng, có câu liên miền ("ghi 200k ăn tối với khách và đặt lịch gặp lại thứ 6") → khó viết luật cứng |
| Giá trị | Dùng hằng ngày, tiết kiệm thời gian nhập liệu |
| Khả thi | Claude xử lý tốt tiếng Việt, tool use, đọc ảnh |
| Chi phí khi sai | Ghi sai chi tiêu: sửa được. Gửi nhầm mail: **không thu hồi được** → bắt buộc duyệt |

Kết luận: dùng agent cho phần hiểu yêu cầu và chọn hành động; dùng **code xác định** cho phần tính toán (tổng tiền, xếp lịch, số liệu bản tin) và **luật cứng** cho phần rủi ro (gửi mail, xoá dữ liệu).

## 4. Yêu cầu chức năng
### Finance
- Ghi thu/chi theo danh mục: ăn uống, di chuyển, mua sắm, giải trí, khác (chi); thu nhập, phụ cấp gia đình (thu).
- Báo cáo: tổng chi, tổng thu, **chi ròng = chi − thu**, theo ngày/tuần/tháng/danh mục; ngân sách và cảnh báo.
- Nhập bằng chữ, ảnh hóa đơn, giọng nói; giao dịch từ ảnh/giọng nói chờ xác nhận.

### Schedule
- Tạo/sửa/xoá sự kiện theo yêu cầu; tìm khung trống; gợi ý xếp việc theo deadline và ưu tiên.
- Nhắc lịch qua Telegram; đồng bộ 2 chiều Google Calendar.

### Email
- Thu thập mail định kỳ, tóm tắt, phân loại; soạn nháp trả lời.
- **Chỉ gửi khi người dùng duyệt** (Telegram hoặc web), có cảnh báo người nhận mới và thông tin nhạy cảm.

### Chung
- Telegram: nhận chữ/ảnh/giọng nói, nút duyệt, bản tin 7h và tổng kết 21h, lệnh `/trace`.
- Website: tổng quan, chi tiêu, lịch, duyệt, **Agent Runs (xem chính xác prompt + tool từng bước)**, AgentOps, cài đặt; cập nhật realtime.

## 5. Yêu cầu phi chức năng
| Nhóm | Yêu cầu ban đầu (xem lại sau bước 6 khi có số liệu thật) |
|---|---|
| Minh bạch | 100% lần gọi LLM và tool được ghi trace đầy đủ |
| An toàn | 0 hành động `external`/`destructive` khi chưa duyệt |
| Riêng tư | Chỉ chủ hệ thống truy cập; audio xử lý local; token mã hoá |
| Chi phí | Có ngân sách ngày cho LLM, cảnh báo khi vượt |
| Độ trễ | Phản hồi Telegram đủ nhanh để dùng khi đang di chuyển — đo p50/p95 từ bước 6 |
| Tái sử dụng | `harness/` không phụ thuộc nghiệp vụ |

## 6. KPI
- Finance: ≥ 95% đúng số tiền, ≥ 90% đúng danh mục (eval).
- Schedule: 0 lịch chồng chéo; ≥ 90% hiểu đúng ngày giờ tiếng Việt.
- Email: 100% ca an toàn đạt.
- Toàn hệ thống: eval tổng ≥ 90% trước mỗi lần release prompt.

## 7. Ngoài phạm vi (phiên bản đầu)
Nhiều người dùng; tư vấn đầu tư; kết nối trực tiếp ngân hàng; app di động riêng.

## 8. Rủi ro chính
| Rủi ro | Biện pháp |
|---|---|
| Prompt injection qua email/ảnh | Dữ liệu không tin cậy + duyệt bắt buộc + policy engine |
| Ghi sai dữ liệu | Hỏi lại khi mơ hồ, xác nhận với ảnh/giọng nói, eval |
| Chi phí tăng | Prompt caching, effort theo agent, ngân sách ngày, metrics |
| Lộ token/bí mật | `.env` không commit, mã hoá token, allowlist chat_id |
