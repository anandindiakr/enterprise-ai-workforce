"""HRIS connector (Workday / BambooHR / Personio over MCP)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class HRISConnector(HttpMCPConnector):
    name = "hris"
    department = "hr"
