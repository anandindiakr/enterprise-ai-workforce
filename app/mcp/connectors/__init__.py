"""Concrete MCP connectors for SaaS systems.

Each connector implements :class:`app.mcp.base.MCPConnector`. Where an
official MCP server is available the connector simply forwards over HTTP/SSE;
otherwise the connector wraps the SaaS REST API in MCP-shaped tools.
"""
