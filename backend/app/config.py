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
    # Model used to extract evidence from uploaded bid PDFs. Extraction runs
    # in AI mode only when ANTHROPIC_API_KEY is set; otherwise rule-based.
    extraction_model: str = "claude-sonnet-5-5"

    # Uploaded bid PDFs: per-file size limit.
    max_upload_mb: int = 10

    database_url: str = "sqlite:///./bidguard.db"
    storage_dir: str = "./storage"

    frontend_origin: str = "http://localhost:5173"

    @property
    def storage_path(self) -> Path:
        p = (BACKEND_DIR / self.storage_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
