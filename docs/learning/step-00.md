# Bước 0 — Khung dự án và tài liệu nền
- Ngày: 2026-11-12 · Git tag: `step-00`

## Đã làm
- Tạo cấu trúc thư mục theo 7 harness; mỗi package có docstring ghi rõ trách nhiệm và bước xây dựng.
- Viết `README.md`, `CLAUDE.md`, `docs/01-requirements.md` (PRD), agent card `AGENT.md` cho 5 agent.
- Viết ADR-0001 (dùng ADR) và mẫu ADR.
- `pyproject.toml` chỉ với thư viện tối thiểu; một smoke test; CI chạy `ruff` + `pytest`.
- `git init`, commit đầu tiên.

## Khái niệm cần nắm
1. **Tài liệu trước code:** PRD trả lời *làm gì* và *thế nào là thành công*; ADR trả lời *vì sao chọn cách này*. Code chỉ trả lời *làm thế nào*.
2. **"Có thật sự cần agent không?"** — 4 tiêu chí: độ phức tạp, giá trị, khả thi, chi phí khi sai. Dự án này dùng agent cho phần hiểu ngôn ngữ, nhưng dùng code xác định cho phần tính toán và luật cứng cho phần rủi ro.
3. **Agent card vs prompt:** `AGENT.md` là spec cho người; `prompt.md` là thứ model đọc. Tách ra để spec ổn định trong khi prompt được tinh chỉnh qua eval.
4. **Ranh giới thư mục là kiến trúc:** `harness/` không import nghiệp vụ → tái sử dụng được.

## Câu hỏi tự kiểm tra
1. Vì sao phần "tổng chi tháng" nên do code tính chứ không để LLM tính?
2. Nếu chỉ viết "không được gửi mail khi chưa duyệt" trong prompt thì rủi ro gì có thể xảy ra?
3. Khi đổi ý về một quyết định đã có ADR, ta làm gì với ADR cũ?

## Bài tập
Đọc `docs/01-requirements.md` và bổ sung **ít nhất 1 yêu cầu hoặc KPI** bạn thấy còn thiếu cho nhu cầu thật của mình.

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
