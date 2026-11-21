"""Model dự phòng: 429 → chuyển model kế tiếp; lỗi khác ném ngay; model hết quota được "nghỉ" — không gọi mạng."""

from types import SimpleNamespace

import pytest
from google.genai import errors

from app.harness.orchestration.llm_client import GeminiClient


def quota() -> errors.ClientError:
    return errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}})


def overloaded(code: int = 503) -> errors.ServerError:
    return errors.ServerError(code, {"error": {"code": code, "status": "UNAVAILABLE", "message": "high demand"}})


def fake_response(text: str):
    part = SimpleNamespace(thought=False, function_call=None, text=text)
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]), finish_reason=None)
    return SimpleNamespace(candidates=[candidate], usage_metadata=None, prompt_feedback=None)


def client_with(behaviour: dict) -> tuple[GeminiClient, list[str]]:
    """behaviour: model → Exception (ném) hoặc str (trả lời). Ghi lại thứ tự model đã gọi."""
    client = GeminiClient(api_key="test-key", model="main", fallback_models=["lite-a", "lite-b", "main"])
    calls: list[str] = []

    def generate_content(model, contents, config):
        calls.append(model)
        outcome = behaviour[model]
        if isinstance(outcome, Exception):
            raise outcome
        return fake_response(outcome)

    client._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return client, calls


def test_primary_used_when_available():
    client, calls = client_with({"main": "ok"})
    assert client.models == ["main", "lite-a", "lite-b"]  # bỏ trùng, giữ thứ tự
    assert client.generate("sys", [], []).text == "ok" and calls == ["main"] and client.model == "main"


def test_quota_error_switches_to_next_model_and_remembers():
    client, calls = client_with({"main": quota(), "lite-a": quota(), "lite-b": "từ lite-b"})
    assert client.generate("sys", [], []).text == "từ lite-b"
    assert calls == ["main", "lite-a", "lite-b"] and client.model == "lite-b"  # trace ghi đúng model thật
    client.generate("sys", [], [])
    assert calls[-1] == "lite-b" and calls.count("main") == 1  # model hết quota đang "nghỉ" → không gọi lại


def test_overload_error_switches_to_next_model():
    """Gặp thật 18/11: "503 UNAVAILABLE ... high demand" trên model chính → đổi sang model dự phòng
    ngay, không chờ hết giờ như lỗi hết quota (xem test_overload_cooldown_is_shorter_than_quota)."""
    client, calls = client_with({"main": overloaded(503), "lite-a": "từ lite-a"})
    assert client.generate("sys", [], []).text == "từ lite-a"
    assert calls == ["main", "lite-a"] and client.model == "lite-a"


def test_overload_cooldown_is_shorter_than_quota(monkeypatch):
    import time as time_module

    client, calls = client_with({"main": overloaded(504), "lite-a": "ok"})
    client.generate("sys", [], [])
    clock = time_module.monotonic() + client.overload_cooldown_s + 1
    monkeypatch.setattr("app.harness.orchestration.llm_client.time.monotonic", lambda: clock)
    client.generate("sys", [], [])
    # Hết thời gian nghỉ NGẮN (quá tải, không phải hết quota) → thử lại model chính ngay (vẫn quá tải
    # trong test này nên lại chuyển tiếp sang dự phòng, khác với việc phải chờ cả giờ như hết quota).
    assert calls == ["main", "lite-a", "main", "lite-a"]


def test_other_errors_are_not_masked():
    bad_request = errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "x"}})
    client, calls = client_with({"main": bad_request, "lite-a": "không được tới đây"})
    with pytest.raises(errors.ClientError) as e:
        client.generate("sys", [], [])
    assert e.value.code == 400 and calls == ["main"]


def test_all_exhausted_raises_429_for_friendly_message():
    client, calls = client_with({"main": quota(), "lite-a": quota(), "lite-b": quota()})
    with pytest.raises(errors.ClientError) as first:
        client.generate("sys", [], [])
    assert first.value.code == 429 and calls == ["main", "lite-a", "lite-b"]
    with pytest.raises(errors.ClientError) as again:  # tất cả đang nghỉ → báo ngay, không gọi mạng
        client.generate("sys", [], [])
    assert again.value.code == 429 and len(calls) == 3


def test_all_overloaded_does_not_report_quota_message():
    """Lỗi thật có thể gặp: cả 3 model cùng quá tải (503), không phải hết quota. Lần gọi THỨ HAI (candidates
    rỗng ngay từ đầu vì tất cả còn đang "nghỉ") phải ném lại đúng lỗi quá tải — không được báo nhầm
    "hết quota" (chat.py đọc code==429 để hiện "Hết lượt gọi AI hôm nay", sai nếu lý do thật là quá tải)."""
    client, calls = client_with({"main": overloaded(503), "lite-a": overloaded(503), "lite-b": overloaded(503)})
    with pytest.raises(errors.ServerError):
        client.generate("sys", [], [])
    with pytest.raises(errors.ServerError) as again:
        client.generate("sys", [], [])
    assert again.value.code == 503 and len(calls) == 3


def test_cooldown_expires(monkeypatch):
    import time as time_module

    client, calls = client_with({"main": quota(), "lite-a": "ok", "lite-b": "ok"})
    client.generate("sys", [], [])
    clock = time_module.monotonic() + client.cooldown_s + 1
    monkeypatch.setattr("app.harness.orchestration.llm_client.time.monotonic", lambda: clock)
    client.generate("sys", [], [])
    # Hết thời gian nghỉ → thử lại model chính (vẫn hết quota) → lại chuyển sang dự phòng.
    assert calls == ["main", "lite-a", "main", "lite-a"]


def test_explicit_model_has_no_fallback(monkeypatch):
    from app.bootstrap import make_llm
    from app.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "lite-a,lite-b")
    get_settings.cache_clear()
    assert make_llm().models[1:] == ["lite-a", "lite-b"]
    assert make_llm("model-for-benchmark").models == ["model-for-benchmark"]  # eval/benchmark: không đổi model
    get_settings.cache_clear()
