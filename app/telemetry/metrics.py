"""Prometheus metrics for chat, voice, agent, and MCP layers."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry(auto_describe=True)

# --- Chat / agent ---
chat_requests_total = Counter(
    "workforce_chat_requests_total",
    "Total chat requests",
    ["department", "status"],
    registry=REGISTRY,
)
chat_latency_seconds = Histogram(
    "workforce_chat_latency_seconds",
    "End-to-end chat latency",
    ["department"],
    registry=REGISTRY,
)
agent_invocations_total = Counter(
    "workforce_agent_invocations_total",
    "Agent invocation count",
    ["agent", "outcome"],
    registry=REGISTRY,
)
swarm_executions_total = Counter(
    "workforce_swarm_executions_total",
    "Swarm strategy executions",
    ["strategy", "department"],
    registry=REGISTRY,
)

# --- Voice ---
voice_sessions_active = Gauge(
    "workforce_voice_sessions_active",
    "Active real-time voice sessions",
    registry=REGISTRY,
)
voice_turn_latency_seconds = Histogram(
    "workforce_voice_turn_latency_seconds",
    "Latency from end-of-user-speech to first TTS chunk",
    ["provider"],
    registry=REGISTRY,
)
voice_provider_errors_total = Counter(
    "workforce_voice_provider_errors_total",
    "Voice provider errors",
    ["provider", "kind"],
    registry=REGISTRY,
)

# --- MCP ---
mcp_tool_calls_total = Counter(
    "workforce_mcp_tool_calls_total",
    "MCP tool invocations",
    ["connector", "tool", "outcome"],
    registry=REGISTRY,
)
mcp_tool_latency_seconds = Histogram(
    "workforce_mcp_tool_latency_seconds",
    "MCP tool latency",
    ["connector", "tool"],
    registry=REGISTRY,
)

# --- Escalations ---
escalations_total = Counter(
    "workforce_escalations_total",
    "Human escalations",
    ["department", "level"],
    registry=REGISTRY,
)
