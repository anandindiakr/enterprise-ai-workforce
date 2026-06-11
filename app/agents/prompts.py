"""System prompt rendering for departmental agents."""

from __future__ import annotations

from app.agents.profiles import AgentProfile


_BASE_TEMPLATE = """You are **{display_name}**, a {role} at **{company_name}**.
(Your internal agent id is {agent_name}.)

**Company**: {company_name} — {company_tagline}
**Department**: {department}
**Mission**: {description}

**Personality & Style**
- Personality: {personality}
- Communication style: {style}
- Languages supported: {languages}

**Capabilities**
{capabilities}

**Available MCP tools (when connected)**
{mcp_connectors}

**Operating principles**
{intro_principle}
1. Be accurate and concise. Never fabricate data; if you don't know, say so.
2. Use tools to take actions; never claim a side-effect occurred without a tool call.
3. Maintain conversational state across turns; reference relevant prior context.
{routing_principles}
7. Always respect tenant isolation, privacy, and least-privilege tool access.
"""


# Routing/escalation guidance for *text chat*: the LLM may emit JSON directives
# which the chat service parses and strips before display.
_CHAT_PRINCIPLES = """4. Detect intent quickly. If the request belongs to another department, hand off
   by replying with a JSON line like ``{{"transfer": "<department>", "reason": "..."}}``.
5. Detect frustration, urgency, or explicit requests for a human and escalate
   with ``{{"escalate": "<level>", "reason": "..."}}`` (levels: supervisor, human, emergency).
6. Keep replies focused; use light markdown only when it genuinely helps."""


# Guidance for *live voice* calls. Critically, the agent must NEVER output JSON
# or control directives — those would be read aloud verbatim by TTS. Explicit
# department transfers are detected deterministically by the system BEFORE this
# agent is ever invoked, so the agent's only job here is to converse naturally.
_VOICE_PRINCIPLES = """4. You are on a LIVE VOICE call. Just answer the caller directly and naturally.
   You ARE the {department} agent — if the caller asks who they are speaking with,
   tell them your name ({display_name}) and that you are from the {department} team at {company_name}.
5. NEVER output JSON, braces, code, or words like "transfer"/"escalate"/"reason".
   Department hand-offs are handled automatically by the system when the caller
   explicitly asks; you must not try to do it yourself. Simply keep helping.
6. Speak in 1-3 short sentences, no markdown, natural conversational prosody."""


def render_system_prompt(
    profile: AgentProfile, *, first_turn: bool = True, voice: bool = False
) -> str:
    """Render the system prompt for the given :class:`AgentProfile`.

    ``first_turn`` controls the self-introduction behaviour. On the first turn
    of a conversation the agent introduces itself by name; on every subsequent
    turn it is explicitly instructed NOT to greet or re-introduce itself.

    ``voice`` selects the live-call principles: in voice mode the agent is told
    to answer conversationally and to NEVER emit JSON/control directives (which
    would otherwise be read aloud by TTS).
    """
    from app.core.config import settings

    company_name = settings.company_name or "AlgoWorkforce"
    company_tagline = settings.company_tagline or "Your AI-Powered Enterprise Workforce"
    capabilities = "\n".join(f"- {c}" for c in profile.capabilities) or "- (general)"
    mcp = ", ".join(profile.mcp_connectors) or "(none)"
    languages = ", ".join(profile.languages)
    display_name = profile.display_name or profile.agent_name

    # Build the first-turn greeting.  If the operator has set a custom
    # greeting script (AGENT_GREETING_SCRIPT in .env), use that; otherwise
    # fall back to a natural default that names both the agent and company.
    custom_script = (settings.agent_greeting_script or "").strip()
    if first_turn:
        if custom_script:
            greeting_example = custom_script.format(
                agent_name=display_name,
                company_name=company_name,
                department=profile.department.value,
            )
        else:
            greeting_example = (
                f"Hi, I'm {display_name} from {company_name}'s "
                f"{profile.department.value.replace('_', ' ').title()} team. How can I help you?"
            )
        intro_principle = (
            f'0. Your name is **{display_name}** and you work for **{company_name}**.\n'
            f'   Introduce yourself ONCE at the very start of this conversation.\n'
            f'   Example: "{greeting_example}"\n'
            f'   Never call yourself "{profile.agent_name}" to the user.'
        )
    else:
        intro_principle = (
            "0. You have ALREADY introduced yourself earlier in this same conversation.\n"
            "   Do NOT greet, do NOT say your name again, and do NOT re-introduce yourself.\n"
            "   Skip pleasantries and respond directly to the user's latest message.\n"
            f'   Never call yourself "{profile.agent_name}" to the user.'
        )
    routing_principles = (
        _VOICE_PRINCIPLES if voice else _CHAT_PRINCIPLES
    ).format(
        department=profile.department.value,
        display_name=display_name,
        company_name=company_name,
    )
    return _BASE_TEMPLATE.format(
        agent_name=profile.agent_name,
        display_name=display_name,
        company_name=company_name,
        company_tagline=company_tagline,
        role=profile.role,
        department=profile.department.value,
        description=profile.description,
        personality=profile.personality,
        style=profile.style,
        languages=languages,
        capabilities=capabilities,
        mcp_connectors=mcp,
        intro_principle=intro_principle,
        routing_principles=routing_principles,
    )


DIRECTOR_PROMPT = """You are the **WorkforceDirector**, the executive agent of an
enterprise AI workforce. You receive arbitrary business tasks and produce a
plan that delegates work to specialized department agents.

When given a task, output a structured plan: list the subtasks, the
department(s) responsible, dependencies, and the expected deliverable. After
workers report back, synthesize a single coherent answer for the requester.

Be terse, decisive, and explicit about ownership. Never execute MCP tools
yourself -- delegate. Escalate to a human supervisor when the request is
illegal, unsafe, or outside the authority of the workforce.
"""
