"""Ticketing connector (Jira / ServiceNow / Linear / Zendesk)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class TicketingConnector(HttpMCPConnector):
    name = "ticketing"
    department = "technology"
