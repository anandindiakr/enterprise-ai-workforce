"""Generic HTTP-backed MCP connector implementing the MCP JSON-RPC surface.

Real MCP servers speak JSON-RPC 2.0 over stdio or HTTP/SSE. This base class
supports the HTTP variant and is reused by every concrete connector. For
local/stdio MCP servers, swap the transport in ``_invoke``.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.exceptions import MCPError
from app.core.logging import logger
from app.mcp.base import MCPConnector, MCPTool


class HttpMCPConnector(MCPConnector):
    """JSON-RPC over HTTP MCP transport."""

    timeout_s: float = 20.0

    def __init__(self, base_url: str, token: str | None = None) -> None:
        super().__init__(base_url, token)
        self._http: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if not self.is_configured:
            return
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        # Do NOT set base_url on the client so that we always use explicit full URLs
        self._http = httpx.AsyncClient(
            headers=headers, timeout=self.timeout_s
        )

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            raise MCPError(f"{self.name} connector not connected")
        return self._http

    async def discover_tools(self) -> list[MCPTool]:
        """Issue ``tools/list`` over JSON-RPC."""
        if not self.is_configured:
            return []
        try:
            resp = await self._jsonrpc("tools/list", {})
            tools_payload = resp.get("tools", [])
            tools = [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                )
                for t in tools_payload
            ]
            self._tools = {t.name: t for t in tools}
            logger.info("{} discovered {} tools", self.name, len(tools))
            return tools
        except Exception as exc:
            logger.warning("{} tool discovery failed: {}", self.name, exc)
            return []

    async def _invoke(self, tool: str, arguments: dict[str, Any]) -> Any:
        resp = await self._jsonrpc("tools/call", {"name": tool, "arguments": arguments})
        return resp.get("content", resp)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    async def _jsonrpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        r = await self.http.post(str(self.base_url), json=payload)
        if r.status_code >= 400:
            raise MCPError(f"{self.name} HTTP {r.status_code}: {r.text}")
        body = r.json()
        if "error" in body:
            raise MCPError(f"{self.name} JSON-RPC error: {body['error']}")
        return body.get("result", {})
