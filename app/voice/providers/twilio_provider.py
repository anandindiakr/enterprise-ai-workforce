"""Twilio voice provider for inbound/outbound phone calls.

Generates TwiML responses that bridge a phone call to our internal voice
WebSocket via ``<Connect><Stream>``, enabling the Workforce platform to
power real PSTN calls.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import VoiceProviderError


class TwilioVoiceProvider:
    name = "twilio"

    def __init__(self) -> None:
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.phone_number = settings.twilio_phone_number

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def inbound_twiml(self, *, ws_url: str, greeting: str | None = None) -> str:
        """Return TwiML to bridge an inbound call to our media stream."""
        try:
            from twilio.twiml.voice_response import Connect, Start, VoiceResponse  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise VoiceProviderError(f"twilio package unavailable: {exc}") from exc

        response = VoiceResponse()
        if greeting:
            response.say(greeting)
        connect = Connect()
        connect.stream(url=ws_url)
        response.append(connect)
        return str(response)

    def place_call(self, to: str, *, twiml_url: str) -> str:
        if not self.is_configured():
            raise VoiceProviderError("Twilio not configured")
        try:
            from twilio.rest import Client  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise VoiceProviderError(f"twilio package unavailable: {exc}") from exc

        client = Client(self.account_sid, self.auth_token)
        call = client.calls.create(to=to, from_=self.phone_number, url=twiml_url)
        return call.sid
