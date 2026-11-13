# ADR-0015: Chuyển giọng nói → chữ ngay trên máy bằng faster-whisper
- Trạng thái: Accepted
- Ngày: 2026-11-14
- Bước: 18

## Bối cảnh
Nhắn thoại trên Telegram ("trưa nay ăn phở bốn lăm nghìn") nhanh hơn gõ. Cần đổi âm thanh (ogg/opus) thành chữ rồi xử lý như tin gõ.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Gửi âm thanh cho Gemini (audio input) | Không cài gì; chất lượng tốt | Giọng nói (dữ liệu sinh trắc, nhạy cảm) rời máy; tốn quota 20 request/ngày |
| B. API speech-to-text trả phí (Google STT, OpenAI) | Chất lượng tốt, nhanh | Tốn tiền, dữ liệu rời máy, thêm một nhà cung cấp |
| C. **faster-whisper local** (CPU, int8) | Miễn phí, riêng tư, không phụ thuộc mạng/quota | Chậm hơn trên CPU, tốn RAM; model tải lần đầu (small ~460MB) |

## Quyết định
**C**, là gói tuỳ chọn `pip install -e "backend[voice]"` (không cài thì bot báo "chưa bật nhận giọng nói").
- `WHISPER_MODEL` (mặc định `small`; `medium` chính xác hơn với tiếng Việt nhưng chậm hơn), `language="vi"`, lọc khoảng lặng (VAD).
- **Hiện lại câu đã nghe** ("🎙 Mình nghe: «…»") trước câu trả lời → nghe sai thì người dùng thấy ngay.
- Chặn trước khi tốn CPU: tin > 120 giây bị từ chối; độ tin cậy thấp / rỗng → nhờ nói lại, **không** đưa cho agent.
- Tự giải mã âm thanh bằng PyAV (`decode_audio`) thay vì để faster-whisper làm — bài học thật: faster-whisper 1.2 gọi tham số PyAV đã bị bỏ ở PyAV 19 → lỗi khi chạy; tự giải mã thì không phụ thuộc phiên bản.

## Hệ quả
- Tin thoại 5–10 giây mất vài giây trên CPU với model small.
- Test tự động dùng transcriber giả; `RUN_WHISPER_TEST=1` chạy thử model tiny thật.
