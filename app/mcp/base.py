"""Base MCP connector abstractions."""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import MCPError
from app.core.logging import logger
from app.telemetry.metrics import mcp_tool_calls_total, mcp_tool_latency_seconds


@dataclass(slots=True)
class MCPTool:
    """Description of a single MCP tool exposed by a connector."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    requires_scopes: tuple[str, ...] = ()


@dataclass(slots=True)
class MCPToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: int = 0
    tool: str = ""
    connector: str = ""


class MCPConnector(abc.ABC):
    """Base class for an MCP-style integration connector.

    Subclasses implement :meth:`discover_tools` and :meth:`call_tool`.
    A connector is a thin, async, audited wrapper around a remote MCP server
    or an internal SaaS API exposing MCP-compatible tools.
    """

    name: str = "abstract"
    department: str = "shared"

    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url
        self.token = token
        self._tools: dict[str, MCPTool] = {}

    # ---- Lifecycle -----------------------------------------------------

    async def connect(self) -> None:  # pragma: no cover - default no-op
        return None

    async def close(self) -> None:  # pragma: no cover
        return None

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    # ---- Tool surface --------------------------------------------------

    @abc.abstractmethod
    async def discover_tools(self) -> list[MCPTool]:
        """Return tool metadata exposed by the underlying MCP server."""

    @abc.abstractmethod
    async def _invoke(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Provider-specific raw invocation, returns serializable result."""

    async def call_tool(
        self, tool: str, arguments: dict[str, Any] | None = None
    ) -> MCPToolResult:
        """Call ``tool`` on this connector with structured telemetry."""
        arguments = arguments or {}
        if not self.is_configured:
            return MCPToolResult(
                success=False,
                error=f"Connector {self.name} not configured",
                tool=tool,
                connector=self.name,
            )

        start = time.perf_counter()
        try:
            data = await self._invoke(tool, arguments)
            duration_ms = int((time.perf_counter() - start) * 1000)
            mcp_tool_calls_total.labels(self.name, tool, "success").inc()
            mcp_tool_latency_seconds.labels(self.name, tool).observe(duration_ms / 1000)
            return MCPToolResult(
                success=True,
                data=data,
                duration_ms=duration_ms,
                tool=tool,
                connector=self.name,
            )
        except MCPError as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            mcp_tool_calls_total.labels(self.name, tool, "error").inc()
            logger.warning("MCP call {}::{} failed: {}", self.name, tool, exc)
            return MCPToolResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
                tool=tool,
                connector=self.name,
            )
        except Exception as exc:  # pragma: no cover - defensive
            duration_ms = int((time.perf_counter() - start) * 1000)
            mcp_tool_calls_total.labels(self.name, tool, "error").inc()
            logger.exception("Unhandled MCP error in {}::{}", self.name, tool)
            return MCPToolResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
                tool=tool,
                connector=self.name,
            )

    def cached_tools(self) -> list[MCPTool]:
        return list(self._tools.values())
