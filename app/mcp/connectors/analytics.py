"""Analytics connector (Mixpanel / Amplitude / GA4 / Looker)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class AnalyticsConnector(HttpMCPConnector):
    name = "analytics"
    department = "marketing"
