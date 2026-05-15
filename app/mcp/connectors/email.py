"""Email connector (Gmail / Outlook / SendGrid)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class EmailConnector(HttpMCPConnector):
    name = "email"
    department = "marketing"
