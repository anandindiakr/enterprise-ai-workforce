"""MCP (Model Context Protocol) integration layer.

Provides a uniform abstraction over MCP servers (CRM, HRIS, ERP, ticketing,
etc.). Connectors are pluggable and discoverable at runtime.
"""

from app.mcp.registry import MCPRegistry, mcp_registry
from app.mcp.base import MCPConnector, MCPTool, MCPToolResult

__all__ = ["MCPRegistry", "mcp_registry", "MCPConnector", "MCPTool", "MCPToolResult"]
