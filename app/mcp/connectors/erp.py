"""ERP / Accounting connector (NetSuite / QuickBooks / Xero)."""

from __future__ import annotations

from app.mcp.connectors._http import HttpMCPConnector


class ERPConnector(HttpMCPConnector):
    name = "erp"
    department = "finance"
