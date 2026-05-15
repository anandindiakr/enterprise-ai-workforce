"""MCP connector registry and lifecycle management."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.core.types import Department
from app.mcp.base import MCPConnector, MCPTool, MCPToolResult


class MCPRegistry:
    """Holds all configured MCP connectors and routes calls by department."""

    def __init__(self) -> None:
        self._by_name: dict[str, MCPConnector] = {}
        self._by_department: dict[Department, list[MCPConnector]] = {}

    # ---- Registration --------------------------------------------------

    def register(self, connector: MCPConnector, department: Department) -> None:
        self._by_name[connector.name] = connector
        self._by_department.setdefault(department, []).append(connector)
        logger.info(
            "MCP connector registered: name={} department={} configured={}",
            connector.name,
            department.value,
            connector.is_configured,
        )

    async def initialize_all(self) -> None:
        for c in self._by_name.values():
            if c.is_configured:
                try:
                    await c.connect()
                    await c.discover_tools()
                except Exception as exc:  # pragma: no cover
                    logger.warning("MCP connector {} init failed: {}", c.name, exc)

    async def shutdown_all(self) -> None:
        for c in self._by_name.values():
            try:
                await c.close()
            except Exception:  # pragma: no cover
                pass

    # ---- Lookup --------------------------------------------------------

    def get(self, name: str) -> MCPConnector | None:
        return self._by_name.get(name)

    def for_department(self, department: Department) -> list[MCPConnector]:
        return list(self._by_department.get(department, []))

    def list_tools(self, department: Department | None = None) -> list[tuple[str, MCPTool]]:
        connectors = (
            self._by_department.get(department, [])
            if department
            else list(self._by_name.values())
        )
        out: list[tuple[str, MCPTool]] = []
        for c in connectors:
            for t in c.cached_tools():
                out.append((c.name, t))
        return out

    async def call(
        self,
        connector: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        c = self.get(connector)
        if c is None:
            return MCPToolResult(
                success=False,
                error=f"Unknown connector: {connector}",
                tool=tool,
                connector=connector,
            )
        return await c.call_tool(tool, arguments)


_registry: MCPRegistry | None = None


def mcp_registry() -> MCPRegistry:
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
        _bootstrap(_registry)
    return _registry


def _bootstrap(reg: MCPRegistry) -> None:
    """Register stock connectors based on environment configuration."""
    from app.mcp.connectors.crm import CRMConnector
    from app.mcp.connectors.hris import HRISConnector
    from app.mcp.connectors.erp import ERPConnector
    from app.mcp.connectors.ticketing import TicketingConnector
    from app.mcp.connectors.knowledge import KnowledgeConnector
    from app.mcp.connectors.calendar import CalendarConnector
    from app.mcp.connectors.email import EmailConnector
    from app.mcp.connectors.analytics import AnalyticsConnector

    reg.register(CRMConnector(settings.mcp_crm_url, settings.mcp_crm_token), Department.SALES)
    reg.register(HRISConnector(settings.mcp_hris_url, settings.mcp_hris_token), Department.HR)
    reg.register(ERPConnector(settings.mcp_erp_url, settings.mcp_erp_token), Department.FINANCE)
    reg.register(
        TicketingConnector(settings.mcp_ticketing_url, settings.mcp_ticketing_token),
        Department.TECHNOLOGY,
    )
    reg.register(
        KnowledgeConnector(settings.mcp_knowledge_url, settings.mcp_knowledge_token),
        Department.CUSTOMER_CARE,
    )
    reg.register(
        CalendarConnector(settings.mcp_calendar_url, settings.mcp_calendar_token),
        Department.RECEPTION,
    )
    reg.register(
        EmailConnector(settings.mcp_email_url, settings.mcp_email_token), Department.MARKETING
    )
    reg.register(
        AnalyticsConnector(settings.mcp_analytics_url, settings.mcp_analytics_token),
        Department.MARKETING,
    )
