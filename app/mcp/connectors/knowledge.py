"""Knowledge base connector (Confluence / Notion / Guru)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class KnowledgeConnector(HttpMCPConnector):
    name = "knowledge"
    department = "customer_care"
