"""CRM connector (Salesforce / HubSpot / Pipedrive over MCP)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class CRMConnector(HttpMCPConnector):
    name = "crm"
    department = "sales"
