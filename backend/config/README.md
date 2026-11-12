# config/
Cấu hình mà **code** đọc — model **không** đọc các file này:
- `policies.yaml` — mức rủi ro tool, quy tắc duyệt, giới hạn bước/token/chi phí, giờ yên lặng (bước 11)
- `pricing.yaml` — bảng giá token để tính $/run trong trace và benchmark (bước 6)

Nguyên tắc: điều gì *tuyệt đối không được sai* (vd. gửi mail khi chưa duyệt) phải được chặn ở đây + policy engine, không chỉ viết trong prompt.
