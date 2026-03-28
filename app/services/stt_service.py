import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class STTService:
    def __init__(self):
        self._model = None
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stt")
        self.available: bool = False

    async def initialize(self):
        logger.info(f"Loading Whisper model: {settings.whisper_model}")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._load_model)
        self.available = True
        logger.info("Whisper model ready")

    def _load_model(self):
        from faster_whisper import WhisperModel

        device = settings.whisper_device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        cache_dir = Path(settings.whisper_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        self._model = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=settings.whisper_compute_type,
            download_root=str(cache_dir),
        )

    def _transcribe_sync(
        self,
        audio_np: np.ndarray,
        partial_cb: Optional[Callable] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> str:
        """Full transcription in one executor call — consumes generator in-thread."""
        # M5: fall back to no-VAD if webrtcvad is unavailable on this platform
        try:
            segments, _ = self._model.transcribe(
                audio_np,
                vad_filter=True,
                word_timestamps=False,
                language=None,
            )
        except Exception:
            segments, _ = self._model.transcribe(
                audio_np,
                vad_filter=False,
                word_timestamps=False,
                language=None,
            )

        parts: list[str] = []
        for seg in segments:    # consume lazy generator IN-THREAD
            text = seg.text.strip()
            if not text:
                continue
            parts.append(text)
            # C5/H1: schedule the async coroutine properly from this thread
            if partial_cb and loop:
                asyncio.run_coroutine_threadsafe(partial_cb(text), loop)
        return " ".join(parts).strip()

    async def transcribe(
        self,
        audio_bytes: bytes,
        on_partial: Optional[Callable] = None,
    ) -> str:
        """Transcribe raw Float32LE 16 kHz mono audio bytes."""
        if not self._model:
            raise RuntimeError("STT service not initialised")

        audio_np = np.frombuffer(audio_bytes, dtype=np.float32).copy()
        if len(audio_np) < 1600:   # < 0.1 s — skip
            return ""

        loop = asyncio.get_event_loop()
        async with self._lock:
            # H2: timeout so a hung Whisper call never locks the session forever
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor,
                        self._transcribe_sync,
                        audio_np,
                        on_partial,
                        loop,
                    ),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                logger.error("STT transcription timed out after 60 s")
                return ""
        return result


stt_service = STTService()
