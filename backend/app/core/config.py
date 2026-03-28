from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI-Powered Speech Pronunciation Coach"
    app_env: str = "development"

    database_url: str = "sqlite:///./app.db"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60 * 24

    otp_ttl_seconds: int = 5 * 60
    otp_debug_return: bool = True

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    openai_api_key: str | None = None


settings = Settings()
