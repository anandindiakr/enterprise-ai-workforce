"""Swarms ``Agent`` factory for the platform.

Builds idiomatic Swarms agents from :class:`AgentProfile` records. Tools are
attached via thin Python callables that delegate into the MCP registry, so
the same departmental agent works from chat, voice, and async workflows.
"""

from __future__ import annotations

from typing import Any, Callable

from swarms import Agent

from app.agents.profiles import (
    ALL_DEPARTMENT_PROFILES,
    DIRECTOR_PROFILE,
    PROFILES_BY_DEPARTMENT,
    AgentProfile,
)
from app.agents.prompts import DIRECTOR_PROMPT, render_system_prompt
from app.core.logging import logger
from app.core.types import Department
from app.mcp import mcp_registry


def _make_mcp_tool(connector_name: str) -> Callable[..., Any]:
    """Create a *synchronous* callable bridging Swarms tool calls to MCP.

    Swarms calls tool functions synchronously (no await).  The agent.run()
    itself is offloaded to a thread via asyncio.to_thread(), so there is no
    running event loop in that thread -- asyncio.run() is safe here.
    """

    def _tool(tool: str, **arguments: Any) -> dict[str, Any]:
        """Invoke an MCP tool on the bound connector.

        Args:
            tool: MCP tool name to execute.
            **arguments: JSON-serialisable arguments forwarded to the tool.

        Returns:
            Structured result dictionary with ``success``, ``data``, ``error``.
        """
        import asyncio

        try:
            result = asyncio.run(mcp_registry().call(connector_name, tool, arguments))
            return {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "duration_ms": result.duration_ms,
                "connector": connector_name,
                "tool": tool,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "connector": connector_name,
                "tool": tool,
                "data": None,
            }

    _tool.__name__ = f"mcp_{connector_name}"
    _tool.__doc__ = (
        f"Invoke a tool on the {connector_name} MCP connector. "
        "Pass `tool` (string) and any keyword arguments expected by the remote tool."
    )
    return _tool


def _build_agent(profile: AgentProfile, *, system_prompt: str | None = None) -> Agent:
    # Only attach MCP tools for connectors that are actually configured.
    # When tools are registered on a Swarms Agent, the LLM is expected to respond
    # with tool calls.  If all connectors are unconfigured (no URL) the model will
    # respond with plain text, which Swarms' tool-execution path returns as None.
    reg = mcp_registry()
    tools: list[Callable[..., Any]] = [
        _make_mcp_tool(name)
        for name in profile.mcp_connectors
        if (conn := reg.get(name)) is not None and conn.is_configured
    ]

    agent = Agent(
        agent_name=profile.agent_name,
        agent_description=profile.description,
        system_prompt=system_prompt or render_system_prompt(profile),
        model_name=profile.model,
        max_loops=profile.max_loops,
        temperature=profile.temperature,
        tools=tools or None,
        dynamic_temperature_enabled=False,
        retry_attempts=2,
        autosave=False,
        verbose=False,
        return_step_meta=False,
    )
    logger.debug("Built agent {} (dept={}, model={})", profile.agent_name, profile.department.value, profile.model)
    return agent


def build_department_agent(department: Department) -> Agent:
    """Build a single department agent."""
    profile = PROFILES_BY_DEPARTMENT[department]
    return _build_agent(profile)


def build_all_department_agents() -> dict[Department, Agent]:
    """Build agents for every operational department (excludes the Director)."""
    return {p.department: _build_agent(p) for p in ALL_DEPARTMENT_PROFILES}


def build_director_agent() -> Agent:
    """Build the executive director agent."""
    return _build_agent(DIRECTOR_PROFILE, system_prompt=DIRECTOR_PROMPT)
