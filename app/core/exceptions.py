"""Domain-specific exceptions for the AI Workforce platform."""

from __future__ import annotations


class WorkforceError(Exception):
    """Base error class for the platform."""

    code: str = "workforce_error"
    http_status: int = 500


class ConfigurationError(WorkforceError):
    code = "configuration_error"
    http_status = 500


class AuthenticationError(WorkforceError):
    code = "authentication_error"
    http_status = 401


class AuthorizationError(WorkforceError):
    code = "authorization_error"
    http_status = 403


class RateLimitError(WorkforceError):
    code = "rate_limit"
    http_status = 429


class AgentExecutionError(WorkforceError):
    code = "agent_execution_error"
    http_status = 500


class RoutingError(WorkforceError):
    code = "routing_error"
    http_status = 422


class MCPError(WorkforceError):
    code = "mcp_error"
    http_status = 502


class VoiceProviderError(WorkforceError):
    code = "voice_provider_error"
    http_status = 502


class MemoryError_(WorkforceError):
    code = "memory_error"
    http_status = 500


class EscalationRequired(WorkforceError):
    """Raised when an agent decides a human must take over."""

    code = "escalation_required"
    http_status = 200
