"""Bước 1 — Gọi Gemini lần đầu với một tool, in ra từng message.

Mục tiêu: nhìn tận mắt cơ chế tool use (function calling) mà vòng ReAct (bước 2) sẽ lặp lại:
  1. Gửi câu hỏi + MÔ TẢ tool   → model trả về `function_call`       (Action)
  2. Code của MÌNH chạy tool     → gửi lại `function_response`        (Observation)
  3. Model đọc kết quả           → trả lời cuối bằng text

Cố tình viết tay 2 lượt gọi (không dùng vòng lặp) để thấy rõ từng bước.

Chạy từ thư mục gốc dự án:
    .\\.venv\\Scripts\\python.exe backend\\experiments\\first_tool_call.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")  # để console Windows in đúng tiếng Việt

MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash"
QUESTION = "Bây giờ ở Việt Nam là mấy giờ, và còn bao lâu nữa đến 12 giờ trưa?"

# Model chỉ "thấy" phần mô tả này (name, description, schema) — KHÔNG thấy code của hàm bên dưới.
# Vì vậy description phải nói rõ tool làm gì và KHI NÀO nên dùng.
GET_CURRENT_TIME = types.FunctionDeclaration(
    name="get_current_time",
    description="Lấy ngày giờ hiện tại theo múi giờ. Dùng khi câu trả lời phụ thuộc vào thời điểm hiện tại.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "enum": ["Asia/Ho_Chi_Minh", "UTC"],
                "description": "Múi giờ cần lấy",
            },
        },
        "required": ["timezone"],
    },
)

# Việt Nam không có giờ mùa hè nên offset +7 cố định là đúng; tránh phụ thuộc gói tzdata trên Windows.
UTC_OFFSETS = {"Asia/Ho_Chi_Minh": 7, "UTC": 0}


def get_current_time(tz_name: str) -> str:
    """Code thật của tool — chạy trên máy MÌNH, không phải trên máy chủ Google."""
    tz = timezone(timedelta(hours=UTC_OFFSETS[tz_name]))
    return datetime.now(tz).strftime("%A %d/%m/%Y %H:%M:%S (UTC%z)")


def show(title: str, response: types.GenerateContentResponse) -> None:
    """In từng part của response theo ngôn ngữ ReAct."""
    candidate = response.candidates[0]
    usage = response.usage_metadata
    print(f"\n=== {title} · finish_reason={candidate.finish_reason} · tokens in={usage.prompt_token_count} "
          f"out={usage.candidates_token_count} thinking={usage.thoughts_token_count}")
    for part in candidate.content.parts:
        if part.thought:
            # include_thoughts=True → bản TÓM TẮT suy luận, không phải chuỗi suy nghĩ thô.
            print(f"  [THOUGHT]     {part.text.strip()}")
        elif part.function_call:
            args = json.dumps(part.function_call.args, ensure_ascii=False)
            print(f"  [ACTION]      {part.function_call.name}({args})")
        elif part.text:
            print(f"  [TEXT]        {part.text.strip()}")


def to_jsonable(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    return str(obj)


def main() -> None:
    # Luôn đặt timeout: không có nó, một request bị treo sẽ làm cả chương trình đứng mãi (ms).
    # Retry: 429/503/504 là lỗi TẠM THỜI (quá tải) → thử lại với khoảng chờ tăng dần 2s, 4s, 8s…
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=45_000,
            retry_options=types.HttpRetryOptions(
                attempts=5, initial_delay=2.0, max_delay=20.0, http_status_codes=[429, 500, 503, 504],
            ),
        ),
    )

    # Cấu hình giống nhau ở mọi lượt gọi — cùng với `contents`, đây chính là toàn bộ "prompt".
    config = types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=[GET_CURRENT_TIME])],
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        # SDK Gemini mặc định TỰ chạy hàm Python và giấu vòng lặp đi. Tắt để tự làm từng bước và nhìn thấy nó.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=QUESTION)])]
    print(f"MODEL: {MODEL}\nUSER: {QUESTION}")

    # ---- Lượt 1: model quyết định có cần tool không ----
    r1 = client.models.generate_content(model=MODEL, contents=contents, config=config)
    show("Lượt 1", r1)
    # Khác Claude (stop_reason="tool_use"): Gemini báo finish_reason=STOP ở cả hai trường hợp,
    # nên phải nhìn xem response có function_call hay không.
    if not r1.function_calls:
        print("\nModel trả lời mà không gọi tool. Thử đổi câu hỏi để thấy tool use.")
        return

    # Gửi lại NGUYÊN VẸN nội dung model vừa trả (kể cả thought signature): API không nhớ gì giữa các lần gọi.
    contents.append(r1.candidates[0].content)

    response_parts = []
    for call in r1.function_calls:
        result = get_current_time(call.args["timezone"])
        print(f"  [OBSERVATION] {result}")
        # id nối kết quả với đúng lời gọi (model có thể gọi nhiều tool cùng lúc).
        response_parts.append(types.Part(function_response=types.FunctionResponse(
            id=call.id, name=call.name, response={"result": result},
        )))
    contents.append(types.Content(role="user", parts=response_parts))  # mọi kết quả trong MỘT message

    # ---- Lượt 2: model đọc Observation và trả lời ----
    r2 = client.models.generate_content(model=MODEL, contents=contents, config=config)
    show("Lượt 2", r2)

    # Lưu toàn bộ những gì đã gửi/nhận — tiền thân của tracer ở bước 2 và trang Agent Runs.
    trace_path = ROOT / "backend" / "data" / "traces" / "first_tool_call.json"
    trace = {"model": MODEL, "config": config, "contents": contents, "responses": [r1, r2]}
    trace_json = json.dumps(trace, default=to_jsonable, ensure_ascii=False, indent=2)
    trace_path.write_text(trace_json, encoding="utf-8")
    print(f"\nĐã lưu trace đầy đủ: {trace_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyError:
        print("Thiếu GEMINI_API_KEY trong file .env")
    except errors.ClientError as e:  # lỗi 4xx: key sai, hết quota, sai tên model…
        print(f"Lỗi phía yêu cầu ({e.code}): {e.message}")
    except errors.ServerError as e:  # lỗi 5xx phía Google
        print(f"Lỗi máy chủ ({e.code}): {e.message}")
