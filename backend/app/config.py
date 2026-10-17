from pydantic import Field
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/empath.db"
    api_key: str = Field(default="local-demo-key-change-me", min_length=16)
    enable_research_mode: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]
    max_request_bytes: int = Field(default=1048576, ge=4096)
    max_audio_request_bytes: int = Field(default=9 * 1024 * 1024, ge=4096)
    voice_model_dir: Path = Path("models/voice")
    risk_model_dir: Path = Path("models/risk")
