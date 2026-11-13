# Bước 3 — Tool Registry + Executor
- Ngày: 2026-11-13 · Git tag: `step-03`

## Đã làm
- `harness/tools/registry.py`: decorator `@agent_tool(risk=...)` sinh JSON schema từ **type hint + docstring** bằng pydantic; `ToolRegistry` riêng cho từng agent; mức rủi ro `read | write | destructive | external`.
- `harness/tools/executor.py`: `ToolExecutor` — mọi lời gọi tool đi qua đúng một cửa: tra tool → kiểm tra rủi ro → validate tham số → chạy có timeout → rút gọn output → trace.
- `react_loop.run_react` nhận `ToolExecutor` thay cho danh sách tool tự chế ở bước 2.
- `tests/test_tools.py`: 13 test (schema, validate, enum, tham số thừa/thiếu, chặn tool `external`, timeout, cắt output).
- `experiments/demo_tools.py` (tool demo dùng chung) + `experiments/tool_registry_demo.py`.

## Kết quả chạy thật
Schema model nhìn thấy — **không ai viết tay**, sinh từ `start: Annotated[date, Field(description=...)]`:
```json
{"type": "object", "additionalProperties": false, "required": ["start", "end"],
 "properties": {"start": {"type": "string", "format": "date", "description": "Ngày bắt đầu, dạng YYYY-MM-DD"}, ...}}
```
Executor chặn trước khi tool chạy:
```
✅ days_between(2026-11-13, 2027-01-01)        → 49        (chuỗi đã được đổi thành date trước khi vào hàm)
❌ days_between("13/11/2026", …)              → start: Input should be a valid date… Hãy gọi lại…
❌ days_between(…, inclusive=true)            → inclusive: Extra inputs are not permitted
❌ calculate("__import__('os').system('dir')") → ValueError: Biểu thức không hợp lệ
❌ delete_all_savings_notes()                 → cần người dùng duyệt… Chưa có gì được thực hiện
```
Run thật với Gemini — "Xoá hết ghi chú tiết kiệm của tôi đi.":
```
[ACTION]      delete_all_savings_notes({})
[OBSERVATION] ⛔ … mức rủi ro 'destructive' nên cần người dùng duyệt … Chưa có gì được thực hiện.
[ANSWER]      Hành động này sẽ xoá toàn bộ … không thể khôi phục. Bạn có chắc chắn muốn xoá không?
```
**Model muốn xoá, code không cho.** Đây là "prompt là hướng dẫn, code là luật" ở dạng nhỏ nhất.

## Khái niệm cần nắm
1. **Tool là hợp đồng API.** Model chỉ thấy tên + docstring + schema. Một nguồn sự thật (chữ ký hàm) → schema, validate và hàm không bao giờ lệch nhau. Thiếu docstring/type hint → lỗi ngay lúc import, không phải lúc chạy thật.
2. **Không tin tham số của model.** Model có thể gửi sai định dạng, bịa thêm tham số, hoặc (khi đọc email độc hại) gửi code. Validate bằng pydantic (`extra="forbid"`) và thông báo lỗi **chỉ rõ trường nào sai** để model tự sửa ở bước sau.
3. **Gemini không có "strict mode" như Claude** (`strict: true` đảm bảo schema phía server). Vì vậy validate phía mình là bắt buộc, không phải tuỳ chọn. Pydantic chạy chế độ *lax*: `"49"` → `49`, `"2027-01-01"` → `date` — đủ khoan dung với lỗi vặt, đủ chặt với lỗi thật.
4. **Mức rủi ro là thuộc tính của tool, không phải của prompt.** `destructive`/`external` bị executor chặn bất kể prompt nói gì. Bước 11 thay "chặn" bằng "tạo PendingAction chờ duyệt".
5. **Timeout trong Python chỉ là "thôi chờ".** Thread không bị giết; tool ghi dữ liệu phải tự có timeout ở tầng I/O (DB, HTTP).
6. **Output dài phải cắt và nói rõ đã cắt** — nếu không, một tool trả 1 MB sẽ làm nổ context và tiền.

## Quan sát thú vị
- Model trả lời "Vui lòng xác nhận để tôi tiến hành" — nhưng nếu bạn trả lời "Có", nó sẽ gọi lại và **vẫn bị chặn**, vì hệ thống chưa có cơ chế duyệt. Đây chính là vấn đề bước 11 giải quyết (duyệt bằng nút bấm, thực thi xác định — không để LLM tự "xác nhận").
- Bước 2 của run trên mất 55 giây — các lần retry tự động khi Gemini trả 503. Không có timeout + retry thì run đã chết.

## Quyết định (ADR liên quan)
Không có ADR mới — đây là chi tiết thực hiện của ADR-0003. Lựa chọn "schema sinh từ type hint thay vì viết tay" được ghi trong docstring `registry.py`.

## Câu hỏi tự kiểm tra
1. Vì sao báo lỗi validate phải ghi rõ **tên trường** sai, thay vì chỉ "tham số không hợp lệ"?
2. Nếu prompt viết "không bao giờ xoá dữ liệu", ta có cần mức rủi ro `destructive` ở code nữa không? Vì sao?
3. `create_event` có tham số tên `title`. Đoạn code nào sẽ làm hỏng nó nếu viết ẩu, và test nào bảo vệ?

## Bài tập
1. Thêm tool `convert_currency(amount_vnd: int, to: Literal["USD", "EUR"])` với tỉ giá cố định, chạy step03 và xem schema có `enum`.
2. Sửa `days_between` bỏ docstring → chạy pytest, đọc thông báo lỗi.
3. Hỏi Gemini "Đổi 500k sang đô" và xem trace: model có truyền `500000` (đúng kiểu `int`) không?

## Ghi chú / thắc mắc của tôi
_(bạn tự điền)_
