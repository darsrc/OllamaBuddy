import asyncio
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class SessionState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    LLM_GENERATING = "llm_generating"
    TTS_PLAYING = "tts_playing"
    INTERRUPTED = "interrupted"
    ENROLLING = "enrolling"


@dataclass
class SessionSettings:
    model: str = "qwen2.5:9b"
    temperature: float = 0.7
    top_p: float = 0.9
    num_ctx: int = 4096
    system_prompt: str = "You are a helpful assistant."
    tts_voice: str = "af_heart"
    tts_mode: str = "punctuation"   # word | punctuation | paragraph
    tts_speed: float = 1.0
    voice_id_enabled: bool = False
    search_enabled: bool = False


@dataclass
class ConversationSession:
    ws_id: str
    conversation_id: Optional[str] = None   # created lazily on first message
    state: SessionState = SessionState.IDLE

    # Audio pipeline
    audio_buffer: list = field(default_factory=list)
    enrollment_mode: bool = False
    enrollment_samples: list = field(default_factory=list)
    enrollment_profile_id: Optional[str] = None

    # LLM conversation history (Ollama format)
    messages: list = field(default_factory=list)
    current_speaker_id: Optional[str] = None
    current_message_id: Optional[str] = None

    # Async control
    interrupt_event: asyncio.Event = field(default_factory=asyncio.Event)
    tts_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    llm_task: Optional[asyncio.Task] = None
    tts_task: Optional[asyncio.Task] = None

    # Pluggable chunker (set at WS connect time)
    tts_chunker: Optional[object] = None

    # Settings
    settings: SessionSettings = field(default_factory=SessionSettings)
