# Bước 18 — Tin nhắn thoại (faster-whisper local)
- Ngày: 2026-11-14 · Git tag: `step-18`

## Đã làm
- `integrations/speech.py`: `WhisperTranscriber` (CPU int8, nạp model một lần, `language="vi"`, VAD), `decode_audio` (PyAV → mono 16 kHz), độ tin cậy từ `avg_logprob`.
- `ChatService.handle_voice`: chưa cài / quá 120 giây / nghe không rõ → báo lịch sự, không gọi agent; rõ → xử lý như tin gõ.
- Telegram: nhận voice/audio, trả lời kèm "🎙 Mình nghe: «…»" + nút duyệt nếu có.
- Gói tuỳ chọn `backend[voice]`. Tổng 181 test (1 test chạy Whisper tiny thật với `RUN_WHISPER_TEST=1`).

## Kết quả chạy thật
Whisper tiny chạy trên CPU với 1 giây âm thanh: giải mã + nhận dạng OK. Lần đầu lỗi `av.open() got an unexpected keyword argument 'metadata_errors'` (faster-whisper 1.2 + PyAV 19) → sửa bằng tự giải mã.

## Khái niệm cần nắm
1. **Dữ liệu nhạy cảm xử lý tại chỗ** khi có thể (ADR-0015).
2. **Cho người dùng thấy cái máy đã hiểu** trước khi hành động.
3. **Chặn sớm** (độ dài, độ tin cậy) trước khi tốn tài nguyên/quota.
4. **Chạy thật để bắt lỗi tương thích thư viện** — test với bản giả không thể phát hiện.

## Câu hỏi tự kiểm tra
1. Vì sao câu nghe với độ tin cậy thấp không được gửi cho agent?
2. Đánh đổi giữa model `small` và `medium`?

## Bài tập
`pip install -e "backend[voice]"`, gửi bot một tin thoại "tối qua đi xem phim một trăm hai mươi nghìn".

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
