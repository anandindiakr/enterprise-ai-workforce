"""Calendar connector (Google Calendar / Microsoft 365)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class CalendarConnector(HttpMCPConnector):
    name = "calendar"
    department = "reception"
