# ADR-0004: Tool là lớp mỏng bọc service; con số do code tính
- Trạng thái: Accepted
- Ngày: 2026-11-13
- Bước: 4

## Bối cảnh
Finance Agent là agent đầu tiên chạm dữ liệu thật. Cùng một nghiệp vụ (ghi giao dịch, tính tổng tháng) sẽ được gọi từ: tool của agent (bước 4), CLI (bước 4), web API (bước 13), bản tin sáng/tối (bước 16). Đồng thời báo cáo tiền phải **đúng tuyệt đối** — LLM cộng nhẩm hay quy đổi "tháng trước" có thể sai.

## Các phương án
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Viết nghiệp vụ ngay trong hàm tool | Nhanh, ít file | Web/CLI/bản tin phải viết lại → lệch logic; test nghiệp vụ phải đi qua tầng tool |
| B. Tool mỏng gọi `services/` (nghiệp vụ thuần, không biết LLM) | Một nguồn sự thật; test service không cần LLM; đổi kênh (web, Telegram) không đụng nghiệp vụ | Thêm một lớp |
| C. Cho LLM truy vấn DB trực tiếp (text-to-SQL) | Linh hoạt câu hỏi | Khó kiểm soát quyền ghi/xoá, kết quả khó kiểm chứng, rủi ro injection |

## Quyết định
Chọn **B**.
- `services/finance_service.py`: nghiệp vụ + kiểm tra (số tiền > 0, danh mục hợp lệ, không ghi ngày tương lai), trả pydantic model.
- `agents/finance/tools.py`: mỗi tool = mở phiên DB → gọi đúng một hàm service → trả kết quả. Không có `if` nghiệp vụ.
- **Mọi con số do code tính**: tổng chi, tổng thu, chi ròng, %, và cả khoảng thời gian (`period="last_month"` → code quy ra ngày, LLM không tự cộng trừ ngày).
- Tiền là số nguyên VND dương; thu/chi do `Category.kind` quyết định. Ràng buộc `amount_vnd > 0` đặt cả ở service lẫn DB (`CHECK`).
- DB: SQLAlchemy 2 + SQLite (file `backend/data/app.db`, không commit). Đổi sang PostgreSQL chỉ đổi `DATABASE_URL` (bước 13, kèm Alembic).

## Hệ quả
- Được: 13 test service chạy không cần LLM; CLI `summary`/`list` dùng chung service, cho ra **đúng cùng con số** agent báo.
- Mất: thêm một lớp; câu hỏi lạ ("trung bình mỗi thứ Bảy tiêu bao nhiêu?") cần thêm hàm service thay vì để LLM tự xoay — chấp nhận, vì đúng quan trọng hơn linh hoạt.
- Xem lại khi: nhu cầu hỏi dữ liệu tự do tăng → cân nhắc tool truy vấn chỉ-đọc có giới hạn (nhóm tính năng A, sau này).

## Bằng chứng
Run thật 2026-11-13: "trưa nay ăn phở 45k, đổ xăng 60k, tối qua đi xem phim 120k" → 3 `add_transaction` song song, "tối qua" → `2026-11-12`; "tháng này tôi chi bao nhiêu" → `get_summary(period="this_month")` → 225.000đ, khớp `python -m app.cli summary`.
