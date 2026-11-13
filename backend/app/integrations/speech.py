"""Giọng nói → chữ bằng faster-whisper chạy NGAY TRÊN MÁY (ADR-0015).

Cài: `pip install -e "backend[voice]"`. Lần đầu dùng sẽ tải model (WHISPER_MODEL: tiny ~75MB · small ~460MB ·
medium ~1.5GB — tiếng Việt nên dùng small trở lên). Chạy CPU, int8 (không cần GPU).

Vì sao chạy local thay vì gửi lên API: giọng nói là dữ liệu cá nhân nhạy cảm; local thì miễn phí,
không tốn quota Gemini, và không phụ thuộc mạng. Đổi lại: chậm hơn và tốn RAM.
"""

from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass
from typing import Protocol

MAX_SECONDS = 120  # tin nhắn thoại dài hơn → bảo người dùng chia nhỏ (chống tốn CPU)


@dataclass
class Transcript:
    text: str
    language: str
    duration_s: float
    confidence: float  # 0..1, ước lượng từ avg_logprob của các đoạn

    @property
    def usable(self) -> bool:
        return bool(self.text.strip()) and self.confidence >= 0.35


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, suffix: str = ".ogg") -> Transcript: ...


class WhisperTranscriber:
    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size, self.device, self.compute_type = model_size, device, compute_type
        self._model = None
        self._lock = threading.Lock()  # nạp model một lần; nhiều tin thoại cùng lúc dùng chung

    def _load(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def transcribe(self, audio: bytes, suffix: str = ".ogg") -> Transcript:
        import math

        model = self._load()
        # Ghi file tạm (PyAV giải mã ogg/opus của Telegram từ file) rồi xoá ngay.
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(audio)
            samples = decode_audio(path)
        finally:
            os.unlink(path)
        segments, info = model.transcribe(samples, language="vi", vad_filter=True, beam_size=5)
        segments = list(segments)
        text = " ".join(s.text.strip() for s in segments).strip()
        confidence = (sum(math.exp(s.avg_logprob) for s in segments) / len(segments)) if segments else 0.0
        return Transcript(text=text, language=info.language, duration_s=round(info.duration, 1),
                          confidence=round(confidence, 2))


def decode_audio(path: str, rate: int = 16_000):
    """File âm thanh bất kỳ → mảng float32 mono 16 kHz (định dạng Whisper cần).

    Tự giải mã thay vì để faster-whisper làm: faster-whisper 1.2 gọi `av.open(..., metadata_errors=...)` mà
    PyAV ≥ 15 đã bỏ → lỗi khi chạy thật (đã gặp ở bước 18). Dùng API ổn định của PyAV thì không phụ thuộc phiên bản.
    """
    import av
    import numpy as np

    resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
    chunks = []
    with av.open(path) as container:
        for frame in container.decode(audio=0):
            chunks += [f.to_ndarray() for f in resampler.resample(frame)]
        chunks += [f.to_ndarray() for f in resampler.resample(None)]  # xả phần còn đệm
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks, axis=1).flatten().astype(np.float32) / 32768.0


_default: WhisperTranscriber | None = None


def default_transcriber() -> Transcriber | None:
    """None nếu chưa cài gói voice — bot sẽ báo người dùng thay vì lỗi."""
    global _default
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return None
    if _default is None:
        _default = WhisperTranscriber(os.environ.get("WHISPER_MODEL") or "small")
    return _default
