"""Shared enums, type aliases, and lightweight value objects."""

from __future__ import annotations

from enum import Enum
from typing import TypeAlias
from uuid import UUID

JsonDict: TypeAlias = dict[str, "object"]
SessionId: TypeAlias = str
AgentId: TypeAlias = str
TenantId: TypeAlias = UUID | str


class Department(str, Enum):
    """Enterprise departments mapped to specialized agents."""

    RECEPTION = "reception"
    CUSTOMER_CARE = "customer_care"
    SALES = "sales"
    HR = "hr"
    FINANCE = "finance"
    TECHNOLOGY = "technology"
    MARKETING = "marketing"
    EXECUTIVE = "executive"


class Channel(str, Enum):
    """Communication channels."""

    CHAT = "chat"
    VOICE = "voice"
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"


class Role(str, Enum):
    """Conversation roles."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    SUPERVISOR = "supervisor"
    TOOL = "tool"


class SwarmStrategy(str, Enum):
    """Swarms-supported orchestration strategies."""

    SEQUENTIAL = "SequentialWorkflow"
    CONCURRENT = "ConcurrentWorkflow"
    HIERARCHICAL = "HierarchicalSwarm"
    MIXTURE = "MixtureOfAgents"
    GROUP_CHAT = "GroupChat"
    MAJORITY_VOTING = "MajorityVoting"
    AGENT_REARRANGE = "AgentRearrange"


class EscalationLevel(str, Enum):
    NONE = "none"
    SUPERVISOR = "supervisor"
    HUMAN = "human"
    EMERGENCY = "emergency"
