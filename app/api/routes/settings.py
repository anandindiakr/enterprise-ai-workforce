"""Platform settings & API key management endpoints (admin only)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.crud import upsert_secret, get_all_secrets
from app.models.schemas import Principal
from app.security.auth import require_admin
from app.swarms.router import reload_agents

router = APIRouter(prefix="/settings", tags=["settings"])

# Map of logical key names → env var names + display labels
KNOWN_KEYS: dict[str, str] = {
    "openai_api_key":        "OpenAI API Key",
    "anthropic_api_key":     "Anthropic API Key",
    "deepgram_api_key":      "Deepgram API Key",
    "elevenlabs_api_key":    "ElevenLabs API Key",
    "livekit_api_key":       "LiveKit API Key",
    "livekit_api_secret":    "LiveKit API Secret",
    "livekit_url":           "LiveKit URL",
    "twilio_account_sid":    "Twilio Account SID",
    "twilio_auth_token":     "Twilio Auth Token",
    "twilio_phone_number":   "Twilio Phone Number",
    "azure_speech_key":      "Azure Speech Key",
    "azure_speech_region":   "Azure Speech Region",
    "resend_api_key":        "Resend API Key",
    "smtp_host":             "SMTP Host",
    "smtp_user":             "SMTP User",
    "smtp_password":         "SMTP Password",
    "escalation_email_to":   "Escalation Email Address",
}

ENV_MAP: dict[str, str] = {
    "openai_api_key":      "OPENAI_API_KEY",
    "anthropic_api_key":   "ANTHROPIC_API_KEY",
    "deepgram_api_key":    "DEEPGRAM_API_KEY",
    "elevenlabs_api_key":  "ELEVENLABS_API_KEY",
    "livekit_api_key":     "LIVEKIT_API_KEY",
    "livekit_api_secret":  "LIVEKIT_API_SECRET",
    "livekit_url":         "LIVEKIT_URL",
    "twilio_account_sid":  "TWILIO_ACCOUNT_SID",
    "twilio_auth_token":   "TWILIO_AUTH_TOKEN",
    "twilio_phone_number": "TWILIO_PHONE_NUMBER",
    "azure_speech_key":    "AZURE_SPEECH_KEY",
    "azure_speech_region": "AZURE_SPEECH_REGION",
    "resend_api_key":      "RESEND_API_KEY",
    "smtp_host":           "SMTP_HOST",
    "smtp_user":           "SMTP_USER",
    "smtp_password":       "SMTP_PASSWORD",
    "escalation_email_to": "ESCALATION_EMAIL_TO",
}


class KeyEntry(BaseModel):
    key: str
    label: str
    is_set: bool


class SaveKeysRequest(BaseModel):
    keys: dict[str, str]


@router.get("/keys")
async def get_api_keys(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_admin),
) -> dict:
    """Return which keys are currently configured (values redacted)."""
    db_secrets = await get_all_secrets(db)
    result = []
    for k, label in KNOWN_KEYS.items():
        env_key = ENV_MAP.get(k, k.upper())
        is_set = bool(db_secrets.get(k) or os.environ.get(env_key))
        result.append({"key": k, "label": label, "is_set": is_set})
    return {"keys": result}


@router.post("/keys")
async def save_api_keys(
    body: SaveKeysRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> dict:
    """Persist API keys to the DB and immediately apply to os.environ."""
    saved = []
    for k, v in body.keys.items():
        if not v or k not in KNOWN_KEYS:
            continue
        await upsert_secret(db, key=k, value=v, label=KNOWN_KEYS[k], updated_by=principal.user_id)
        env_key = ENV_MAP.get(k, k.upper())
        os.environ[env_key] = v
        saved.append(k)
    # Bust agent cache so the new OPENAI_API_KEY is picked up on next chat
    if any(k in saved for k in ("openai_api_key", "anthropic_api_key")):
        reload_agents()
    return {"saved": saved, "count": len(saved)}
