"""Application configuration."""

import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App
    APP_NAME: str = "Agent Council API"
    DEBUG: bool = False

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    WORKSPACE_PATH: Path = BASE_DIR.parent
    CHATS_DIR: Path = WORKSPACE_PATH / "chats"
    SESSIONS_DIR: Path = WORKSPACE_PATH / "sessions"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 11111

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Auth
    SECRET_KEY: str = secrets.token_urlsafe(32)
    SESSION_COOKIE_NAME: str = "session_id"
    SESSION_MAX_AGE: int = 7 * 24 * 60 * 60  # 7 days
    CSRF_COOKIE_NAME: str = "csrf_token"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
settings.CHATS_DIR.mkdir(parents=True, exist_ok=True)
settings.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
