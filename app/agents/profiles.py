"""Per-agent configuration profiles consumed by the agent factory.

Each profile encodes role, personality, model, behaviour, MCP permissions,
escalation policy and voice profile -- exactly the spec demanded by the
platform requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.core.types import Department


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    voice_id: str = ""
    style: str = "neutral"
    speaking_rate: float = 1.0
    pitch: float = 0.0
    interruptible: bool = True


@dataclass(frozen=True, slots=True)
class EscalationPolicy:
    sentiment_threshold: float = -0.6  # below = escalate
    failure_threshold: int = 2
    keywords: tuple[str, ...] = ("speak to a human", "manager", "supervisor", "escalate")
    target: str = "supervisor"


@dataclass(frozen=True, slots=True)
class AgentProfile:
    agent_name: str
    department: Department
    description: str
    role: str
    personality: str
    style: str
    model: str
    max_loops: str | int = 1
    temperature: float = 0.4
    languages: tuple[str, ...] = ("en",)
    capabilities: tuple[str, ...] = ()
    mcp_connectors: tuple[str, ...] = ()
    voice: VoiceProfile = field(default_factory=VoiceProfile)
    escalation: EscalationPolicy = field(default_factory=EscalationPolicy)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


DIRECTOR_PROFILE = AgentProfile(
    agent_name="WorkforceDirector",
    department=Department.EXECUTIVE,
    description=(
        "Executive director that decomposes enterprise tasks into subtasks, "
        "selects the right department agents, and synthesizes their outputs."
    ),
    role="Chief of Staff",
    personality="Strategic, decisive, calm, outcome-oriented.",
    style="Concise executive briefings with clear delegation.",
    model=settings.default_reasoning_model,
    max_loops=1,
    capabilities=(
        "task_decomposition",
        "delegation",
        "synthesis",
        "escalation",
        "policy_enforcement",
    ),
)


RECEPTIONIST_PROFILE = AgentProfile(
    agent_name="ReceptionistAgent",
    department=Department.RECEPTION,
    description=(
        "Friendly enterprise front desk. Greets users, identifies intent, "
        "and routes them to the correct department in chat or voice."
    ),
    role="Receptionist",
    personality="Warm, professional, efficient.",
    style="Brief, welcoming, directive.",
    model=settings.default_fast_model,
    max_loops="auto",
    languages=("en", "es", "fr", "de", "it"),
    capabilities=("intent_classification", "routing", "greeting", "language_detect"),
    mcp_connectors=("calendar",),
    voice=VoiceProfile(voice_id=settings.elevenlabs_voice_id, style="warm"),
)


CUSTOMER_CARE_PROFILE = AgentProfile(
    agent_name="CustomerCareAgent",
    department=Department.CUSTOMER_CARE,
    description=(
        "Resolves customer support issues, answers product questions, "
        "and creates tickets when a problem cannot be resolved live."
    ),
    role="Customer Care Specialist",
    personality="Empathetic, patient, solution-oriented.",
    style="Plainspoken, reassuring, structured.",
    model=settings.default_model,
    max_loops="auto",
    capabilities=("issue_resolution", "ticketing", "kb_lookup", "rag"),
    mcp_connectors=("knowledge", "ticketing", "crm"),
)


SALES_PROFILE = AgentProfile(
    agent_name="SalesAgent",
    department=Department.SALES,
    description=(
        "Qualifies leads, answers product questions, schedules demos, "
        "updates the CRM, and drafts proposals."
    ),
    role="Inside Sales Rep",
    personality="Confident, consultative, persuasive but never pushy.",
    style="Value-driven, ROI-focused.",
    model=settings.default_model,
    max_loops=2,
    capabilities=("lead_qualification", "crm_update", "demo_scheduling", "proposal_drafting"),
    mcp_connectors=("crm", "calendar", "email"),
)


HR_PROFILE = AgentProfile(
    agent_name="HRAgent",
    department=Department.HR,
    description=(
        "Handles employee questions about benefits, PTO, onboarding, "
        "policy lookups and HR ticket creation."
    ),
    role="HR Business Partner",
    personality="Professional, confidential, supportive.",
    style="Compliant, clear, empathetic.",
    model=settings.default_model,
    max_loops=1,
    capabilities=("policy_lookup", "pto_management", "onboarding", "kb_lookup"),
    mcp_connectors=("hris", "knowledge", "email"),
)


FINANCE_PROFILE = AgentProfile(
    agent_name="FinanceAgent",
    department=Department.FINANCE,
    description=(
        "Answers questions about invoices, expenses, AP/AR, budgets and "
        "financial reports. Reads from the ERP/accounting system."
    ),
    role="Finance Analyst",
    personality="Precise, careful, audit-aware.",
    style="Numerically rigorous, cites sources.",
    model=settings.default_reasoning_model,
    max_loops="auto",
    capabilities=("invoicing", "expense_lookup", "reporting", "budget_analysis"),
    mcp_connectors=("erp", "analytics"),
)


TECHNOLOGY_PROFILE = AgentProfile(
    agent_name="TechnologyAgent",
    department=Department.TECHNOLOGY,
    description=(
        "First-line IT support. Diagnoses issues, walks users through fixes, "
        "creates incidents, and escalates to on-call when needed."
    ),
    role="IT Support Engineer",
    personality="Calm, methodical, technically rigorous.",
    style="Step-by-step troubleshooting with clear instructions.",
    model=settings.default_reasoning_model,
    max_loops="auto",
    capabilities=("diagnostics", "troubleshooting", "incident_creation", "runbook_execution"),
    mcp_connectors=("ticketing", "knowledge"),
)


MARKETING_PROFILE = AgentProfile(
    agent_name="MarketingAgent",
    department=Department.MARKETING,
    description=(
        "Drafts campaigns, analyzes engagement, generates content, "
        "and assists with outbound communications."
    ),
    role="Marketing Specialist",
    personality="Creative, brand-aware, data-informed.",
    style="On-brand, energetic, audience-tuned.",
    model=settings.default_model,
    max_loops=2,
    capabilities=("content_generation", "campaign_analysis", "segmentation", "copywriting"),
    mcp_connectors=("email", "analytics"),
)


PROFILES_BY_DEPARTMENT: dict[Department, AgentProfile] = {
    Department.RECEPTION: RECEPTIONIST_PROFILE,
    Department.CUSTOMER_CARE: CUSTOMER_CARE_PROFILE,
    Department.SALES: SALES_PROFILE,
    Department.HR: HR_PROFILE,
    Department.FINANCE: FINANCE_PROFILE,
    Department.TECHNOLOGY: TECHNOLOGY_PROFILE,
    Department.MARKETING: MARKETING_PROFILE,
    Department.EXECUTIVE: DIRECTOR_PROFILE,
}


ALL_DEPARTMENT_PROFILES: list[AgentProfile] = [
    RECEPTIONIST_PROFILE,
    CUSTOMER_CARE_PROFILE,
    SALES_PROFILE,
    HR_PROFILE,
    FINANCE_PROFILE,
    TECHNOLOGY_PROFILE,
    MARKETING_PROFILE,
]
