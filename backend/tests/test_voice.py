"""Tin nhắn thoại: chữ nghe được đi tiếp như tin gõ; nghe không rõ / quá dài / chưa cài → báo lịch sự."""

import io
import math
import struct
import wave

import pytest
from fakes import FakeLLM

from app.chat import ChatService
from app.integrations.email_provider import FakeEmailProvider
from app.integrations.speech import Transcript
from app.runtime import Runtime


class FakeTranscriber:
    def __init__(self, transcript: Transcript) -> None:
        self.transcript = transcript
        self.calls = 0

    def transcribe(self, audio: bytes, suffix: str = ".ogg") -> Transcript:
        self.calls += 1
        return self.transcript


def chat(script=()):
    rt = Runtime.create("sqlite://", email_provider=FakeEmailProvider(), llm=FakeLLM(list(script)))
    return ChatService(rt, agent_name="finance"), rt


def test_clear_voice_is_handled_like_text():
    service, rt = chat(["Đã ghi 45.000đ."])
    heard, reply = service.handle_voice("telegram", "1", b"ogg", FakeTranscriber(
        Transcript("trưa nay ăn phở bốn mươi lăm nghìn", "vi", 3.2, 0.82)), duration_s=3)
    assert heard == "trưa nay ăn phở bốn mươi lăm nghìn" and reply.answer == "Đã ghi 45.000đ."
    assert rt.llm.seen_histories[0][0]["text"].endswith(heard)  # agent nhận đúng chữ đã nghe


@pytest.mark.parametrize(("transcriber", "duration", "status"), [
    (None, 3, "disabled"),
    (FakeTranscriber(Transcript("ừm", "vi", 1, 0.2)), 1, "unclear"),
    (FakeTranscriber(Transcript("", "vi", 2, 0.0)), 2, "unclear"),
    (FakeTranscriber(Transcript("x", "vi", 200, 0.9)), 200, "rejected"),
])
def test_unusable_voice_never_reaches_the_agent(transcriber, duration, status):
    service, rt = chat()
    _, reply = service.handle_voice("telegram", "1", b"ogg", transcriber, duration_s=duration)
    assert reply.status == status and rt.llm.seen_histories == []
    if status == "rejected":
        assert transcriber.calls == 0  # quá dài → không tốn CPU chuyển giọng nói


def test_whisper_pipeline_runs_locally_on_silence():
    """Chạy faster-whisper thật (model tiny) trên 1 giây im lặng: kiểm tra giải mã + nạp model hoạt động."""
    pytest.importorskip("faster_whisper")
    import os

    if not os.environ.get("RUN_WHISPER_TEST"):
        pytest.skip("đặt RUN_WHISPER_TEST=1 để chạy (tải model tiny ~75MB lần đầu)")
    from app.integrations.speech import WhisperTranscriber

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(10 * math.sin(i))) for i in range(16000)))
    t = WhisperTranscriber("tiny").transcribe(buf.getvalue(), ".wav")
    assert t.duration_s == pytest.approx(1.0, abs=0.1) and not t.usable
