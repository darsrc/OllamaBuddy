import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
MIN_SAMPLES = int(1.6 * SAMPLE_RATE)   # 1.6 s minimum for embedding


@dataclass
class SpeakerMatch:
    profile_id: str
    label: str
    confidence: float


class SpeakerService:
    def __init__(self):
        self._encoder = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="speaker")
        self.available = False

    async def initialize(self):
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self._load_encoder)
            self.available = True
            logger.info("Speaker encoder loaded")
        except Exception as e:
            logger.warning(f"Speaker service unavailable (voice ID disabled): {e}")
            self.available = False

    def _load_encoder(self):
        from resemblyzer import VoiceEncoder
        self._encoder = VoiceEncoder(device="cpu")

    def _preprocess(self, audio_np: np.ndarray) -> np.ndarray:
        from resemblyzer import preprocess_wav
        return preprocess_wav(audio_np, source_sr=SAMPLE_RATE)

    async def embed_utterance(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        if not self.available:
            return None
        audio_np = np.frombuffer(audio_bytes, dtype=np.float32).copy()
        if len(audio_np) < MIN_SAMPLES:
            return None
        loop = asyncio.get_event_loop()
        try:
            wav = await loop.run_in_executor(self._executor, self._preprocess, audio_np)
            return await loop.run_in_executor(
                self._executor, self._encoder.embed_utterance, wav
            )
        except Exception as e:
            logger.error(f"embed_utterance error: {e}")
            return None

    async def enroll(self, audio_samples: list[bytes]) -> Optional[np.ndarray]:
        """Create a single speaker embedding from multiple audio samples."""
        if not self.available or not audio_samples:
            return None
        loop = asyncio.get_event_loop()
        try:
            wavs: list[np.ndarray] = []
            for raw in audio_samples:
                audio_np = np.frombuffer(raw, dtype=np.float32).copy()
                if len(audio_np) >= MIN_SAMPLES:
                    wav = await loop.run_in_executor(
                        self._executor, self._preprocess, audio_np
                    )
                    wavs.append(wav)
            if not wavs:
                return None
            return await loop.run_in_executor(
                self._executor, self._encoder.embed_speaker, wavs
            )
        except Exception as e:
            logger.error(f"enroll error: {e}")
            return None

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))


speaker_service = SpeakerService()
