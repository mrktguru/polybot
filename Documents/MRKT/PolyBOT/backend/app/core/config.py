"""Application configuration via pydantic-settings.

Loads from environment / .env file. Mirrors the variables defined in
the project spec (`polymarket-bot-strategies.md`) plus app-level additions.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Polymarket ──────────────────────────────────────────
    polygon_private_key: str = ""
    clob_api_key: str = ""
    clob_api_secret: str = ""
    clob_api_passphrase: str = ""
    clob_host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"

    # ── LLM ─────────────────────────────────────────────────
    anthropic_api_key: str = ""
    llm_curator_model: str = "claude-haiku-4-5-20251001"
    llm_analysis_model: str = "claude-sonnet-4-6"

    # ── Infrastructure ──────────────────────────────────────
    database_url: str = "postgresql+psycopg://polybot:polybot@localhost:5432/polybot"
    redis_url: str = "redis://localhost:6379/0"

    # ── Notifications ───────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── External APIs ───────────────────────────────────────
    metaculus_api_key: str = ""
    the_odds_api_key: str = ""

    # ── Trading params ──────────────────────────────────────
    paper_trading: bool = True
    total_capital: float = 500.0
    daily_loss_limit: float = 50.0
    max_drawdown_pct: float = 0.15

    # ── App ─────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"
    sentry_dsn: str = ""
    api_secret_key: str = "change-me-in-production"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
