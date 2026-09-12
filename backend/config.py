import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    # LLM Settings
    LLM_PROVIDER: Literal["gemini", "anthropic", "openai", "ollama"] = "ollama"
    LLM_MODEL: str = "llama3.1:8b"
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 3

    # API Keys & Tokens
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    HF_TOKEN: str = ""

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Vector Store
    VECTOR_STORE_BACKEND: Literal["auto", "postgres", "chroma"] = "auto"
    POSTGRES_USER: str = "civiclens"
    POSTGRES_PASSWORD: str = "civiclens_secret"
    POSTGRES_DB: str = "civiclens_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    CHROMA_PERSIST_DIR: str = "backend/data/chroma_db"

    # HITL
    AUTO_APPROVE_PENDING_AUDIT: bool = False

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Propagate HF_TOKEN to os.environ so transformers / huggingface_hub automatically authenticate
if settings.HF_TOKEN:
    os.environ["HF_TOKEN"] = settings.HF_TOKEN
    os.environ["HUGGING_FACE_HUB_TOKEN"] = settings.HF_TOKEN
