"""Model dự phòng: 429 → chuyển model kế tiếp; lỗi khác ném ngay; model hết quota được "nghỉ" — không gọi mạng."""

from types import SimpleNamespace

import pytest
from google.genai import errors

from app.harness.orchestration.llm_client import GeminiClient


def quota() -> errors.ClientError:
    return errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}})


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
