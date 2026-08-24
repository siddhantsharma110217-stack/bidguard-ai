from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: str = "mock"
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5"

    database_url: str = "sqlite:///./bidguard.db"
    storage_dir: str = "./storage"

    frontend_origin: str = "http://localhost:5173"

    @property
    def storage_path(self) -> Path:
        p = (BACKEND_DIR / self.storage_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
