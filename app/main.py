"""FastAPI application factory + lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import auth as auth_routes
from app.api.routes import chat as chat_routes
from app.api.routes import platform as platform_routes
from app.api.routes import voice as voice_routes
from app.api.ws import chat_ws, voice_ws
from app.core.config import settings
from app.core.exceptions import WorkforceError
from app.core.logging import configure_logging, logger
from app.mcp import mcp_registry
from app.memory.long_term import long_term_memory
from app.memory.short_term import short_term_memory
from app.telemetry.tracing import init_tracing


def _export_llm_keys() -> None:
    """Reflect LLM/voice API keys from pydantic settings back into os.environ.

    LiteLLM (used by Swarms) and most provider SDKs read keys directly from
    os.environ.  When running locally without Docker the keys are in the .env
    file but pydantic-settings does not write them back automatically.
    """
    import os

    key_map = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "DEEPGRAM_API_KEY": settings.deepgram_api_key,
        "ELEVENLABS_API_KEY": settings.elevenlabs_api_key,
        "LIVEKIT_API_KEY": settings.livekit_api_key,
        "LIVEKIT_API_SECRET": settings.livekit_api_secret,
        "LIVEKIT_URL": settings.livekit_url,
        "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
        "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
        "AZURE_SPEECH_KEY": settings.azure_speech_key,
    }
    for env_var, value in key_map.items():
        if value and not os.environ.get(env_var):
            os.environ[env_var] = value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    _export_llm_keys()
    init_tracing()
    logger.info("AI Workforce starting (env={})", settings.app_env)

    # Bring up infra
    await short_term_memory().connect()
    long_term_memory().connect()
    await mcp_registry().initialize_all()

    try:
        yield
    finally:
        logger.info("AI Workforce shutting down")
        await mcp_registry().shutdown_all()
        await short_term_memory().close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Enterprise Multi-Agent AI Workforce Platform with chat + real-time voice.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limit
    limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_min}/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Domain error handler
    @app.exception_handler(WorkforceError)
    async def _workforce_error_handler(_: Request, exc: WorkforceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": str(exc)},
        )

    # Routes
    api_v1 = "/api/v1"
    app.include_router(auth_routes.router, prefix=api_v1)
    app.include_router(chat_routes.router, prefix=api_v1)
    app.include_router(voice_routes.router, prefix=api_v1)
    app.include_router(platform_routes.router, prefix=api_v1)
    app.include_router(chat_ws.router, prefix=api_v1)
    app.include_router(voice_ws.router, prefix=api_v1)

    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": "0.1.0",
            "env": settings.app_env,
            "docs": "/docs",
        }

    return app


app = create_app()
