from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Ollama
    ollama_host: str = "http://localhost:11434"
    default_model: str = "qwen2.5:9b"

    # STT (faster-whisper)
    whisper_model: str = "base"
    whisper_device: str = "auto"     # auto | cpu | cuda
    whisper_compute_type: str = "int8"
    whisper_cache_dir: str = "data/whisper_models"

    # TTS (kokoro-onnx)
    kokoro_model_path: str = "data/voices/kokoro-v1.0.onnx"
    kokoro_voices_path: str = "data/voices/voices-v1.0.bin"
    default_voice: str = "af_heart"
    default_tts_speed: float = 1.0
    default_tts_mode: str = "punctuation"

    # Speaker identification
    speaker_threshold: float = 0.75
    enrollment_samples_required: int = 3

    # Search
    searxng_url: str = "http://localhost:8888"
    search_timeout: float = 10.0

    # Storage
    db_path: str = "sqlite:///./data/ollamabuddy.db"
    avatar_dir: str = "data/avatars"

    # Model downloads — set to false to require manual placement of model files
    auto_download_models: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
