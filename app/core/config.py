"""Centralized typed application configuration.

Loaded once at process start from environment / .env file. All services and
agents read configuration from :data:`settings` -- never directly from
``os.environ``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Top-level platform settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "AI Workforce"
    app_env: Literal["development", "staging", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "INFO"
    app_debug: bool = False

    # --- Security ---
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8h — avoids silent mid-session 401s
    api_key_header: str = "X-API-Key"
    internal_api_key: str = "internal-svc-key"
    cors_origins: str = "http://localhost:3000,http://localhost:4000,http://localhost:8080"

    # --- Persistence ---
    postgres_dsn: str = "postgresql+asyncpg://workforce:workforce@localhost:5432/workforce"
    redis_url: str = "redis://localhost:6379/0"

    # --- Vector store ---
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "workforce_knowledge"
    chroma_persist_dir: str = "./.chroma"  # embedded fallback when no Chroma server

    # --- Background jobs ---
    use_celery: bool = False  # when False, embedding runs in-process (asyncio)

    # --- LLM ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_model: str = "gpt-4o-mini"
    default_fast_model: str = "gpt-4o-mini"
    default_reasoning_model: str = "gpt-4o"

    # --- Voice ---
    deepgram_api_key: str = ""
    azure_speech_key: str = ""
    azure_speech_region: str = "eastus"
    google_application_credentials: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    openai_realtime_model: str = "gpt-4o-realtime-preview"
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    voice_stt_provider: str = "deepgram"
    voice_tts_provider: str = "elevenlabs"
    voice_realtime_provider: str = "openai_realtime"

    # --- MCP integrations ---
    # Defaults point to the built-in mock servers (self-referencing on same app)
    mcp_base_url: str = "http://localhost:8000"  # internal URL (docker: http://api:8000)
    mcp_crm_url: str = ""         # overrides mcp_base_url/mcp/crm if set
    mcp_crm_token: str = ""
    mcp_hris_url: str = ""        # overrides mcp_base_url/mcp/hris if set
    mcp_hris_token: str = ""
    mcp_erp_url: str = ""         # overrides mcp_base_url/mcp/finance if set
    mcp_erp_token: str = ""
    mcp_ticketing_url: str = ""   # overrides mcp_base_url/mcp/devops if set
    mcp_ticketing_token: str = ""
    mcp_knowledge_url: str = ""   # overrides mcp_base_url/mcp/knowledge if set
    mcp_knowledge_token: str = ""
    mcp_calendar_url: str = ""    # overrides mcp_base_url/mcp/calendar if set
    mcp_calendar_token: str = ""
    mcp_email_url: str = ""       # overrides mcp_base_url/mcp/email if set
    mcp_email_token: str = ""
    mcp_analytics_url: str = ""   # overrides mcp_base_url/mcp/analytics if set
    mcp_analytics_token: str = ""

    # --- Email / notifications ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@ai-workforce.io"
    email_from: str = "noreply@ai-workforce.io"
    resend_api_key: str = ""      # alternative to SMTP
    escalation_email_to: str = ""  # on-call team address for escalation alerts

    # --- File upload ---
    upload_dir: str = "/tmp/ai_workforce_uploads"
    max_upload_size_mb: int = 20

    # --- Telemetry ---
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "ai-workforce"
    prometheus_port: int = 9090

    # --- Rate limit ---
    rate_limit_per_min: int = Field(default=120, ge=1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return a cached :class:`AppSettings` instance."""
    return AppSettings()


settings = get_settings()
