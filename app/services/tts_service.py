import asyncio
import logging
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np

from config import settings

logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/voices-v1.0.bin"
)

MIN_TTS_CHARS = 3
SAMPLE_RATE = 24_000


class TTSService:
    def __init__(self):
        self._kokoro = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts")
        self._voices: list[str] = []
        self.available: bool = False

    async def initialize(self):
        model_path = Path(settings.kokoro_model_path)
        voices_path = Path(settings.kokoro_voices_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        if not model_path.exists():
            if not settings.auto_download_models:
                logger.warning(
                    f"Kokoro model not found at {model_path}. "
                    "Set AUTO_DOWNLOAD_MODELS=true or download manually.\n"
                    f"  Model URL: {_MODEL_URL}"
                )
                return
            logger.info("Downloading Kokoro ONNX model (~330 MB)…")
            await self._download(_MODEL_URL, model_path)
        if not voices_path.exists():
            if not settings.auto_download_models:
                logger.warning(f"Kokoro voices file not found at {voices_path}.")
                return
            logger.info("Downloading Kokoro voices file…")
            await self._download(_VOICES_URL, voices_path)

        logger.info("Loading Kokoro TTS model…")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor, self._load_model, str(model_path), str(voices_path)
        )
        self.available = True
        logger.info(f"Kokoro TTS ready — {len(self._voices)} voices")

    async def _download(self, url: str, path: Path):
        import httpx

        async with httpx.AsyncClient(follow_redirects=True, timeout=600) as client:
            async with client.stream("GET", url) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(path, "wb") as f:
                    async for chunk in r.aiter_bytes(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            logger.info(f"  {path.name}: {downloaded/total*100:.1f}%")

    def _load_model(self, model_path: str, voices_path: str):
        from kokoro_onnx import Kokoro

        self._kokoro = Kokoro(model_path, voices_path)
        try:
            self._voices = list(self._kokoro.get_voices())
        except Exception:
            self._voices = ["af_heart", "af_bella", "am_adam", "bm_george"]

    def _synth_blocking(self, text: str, voice: str, speed: float) -> np.ndarray:
        chunks: list[np.ndarray] = []
        try:
            for samples, _sr in self._kokoro.create_stream(
                text, voice=voice, speed=speed
            ):
                if samples is not None and len(samples):
                    chunks.append(samples.astype(np.float32))
        except Exception as e:
            logger.error(f"TTS synth error: {e}")
            return np.array([], dtype=np.float32)
        return np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)

    async def synthesize(
        self, text: str, voice: str, speed: float
    ) -> Optional[np.ndarray]:
        if not self._kokoro:
            raise RuntimeError("TTS service not initialised")
        if len(text.strip()) < MIN_TTS_CHARS:
            return None

        safe_voice = voice if voice in self._voices else settings.default_voice
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor, self._synth_blocking, text, safe_voice, speed
        )
        return result if len(result) else None

    @staticmethod
    def make_audio_frame(audio: np.ndarray, chunk_index: int) -> bytes:
        """Pack Float32 audio into the binary WS frame protocol."""
        header = struct.pack("<IIII", 0x01, SAMPLE_RATE, chunk_index, len(audio))
        return header + audio.tobytes()

    @property
    def available_voices(self) -> list[str]:
        return self._voices or ["af_heart", "af_bella", "am_adam", "bm_george"]


tts_service = TTSService()
