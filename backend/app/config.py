"""
Debate Coach Backend - Configuration
Loads environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://debate:debate_pass@localhost:5432/debate_coach"

    # Auth
    secret_key: str = "change-me-generate-with-openssl-rand-hex-32"

    # Groq API (Cloud Path) — free at console.groq.com
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # Edge Model Paths
    vosk_model_path: str = "models/edge/vosk-model-small-en-us"
    llama_model_path: str = "models/edge/llama-2-7b-chat.Q4_K_M.gguf"

    # VAD
    vad_threshold: float = 0.5

    # Default mode
    default_mode: str = "cloud"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
