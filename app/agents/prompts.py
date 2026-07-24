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


# Routing/escalation guidance for *text chat*
_CHAT_PRINCIPLES = """4. Detect intent quickly. If the request belongs to another department, hand off
   by replying with a JSON line like ``{{"transfer": "<department>", "reason": "..."}}``.
5. Detect frustration, urgency, or explicit requests for a human and escalate
   with ``{{"escalate": "<level>", "reason": "..."}}`` (levels: supervisor, human, emergency).
6. Keep replies focused; use light markdown only when it genuinely helps."""


# Guidance for *live voice* calls — agent must NEVER output JSON (it would be read aloud).
_VOICE_PRINCIPLES = """4. You are on a LIVE VOICE call. Just answer the caller directly and naturally.
   You ARE the {department} agent — if the caller asks who they are speaking with,
   tell them your name ({display_name}) and that you are from the {department} team at {company_name}.
5. NEVER output JSON, braces, code, or words like "transfer"/"escalate"/"reason".
   Department hand-offs are handled automatically by the system when the caller
   explicitly asks; you must not try to do it yourself. Simply keep helping.
6. Speak in 1-3 short sentences, no markdown, natural conversational prosody.
7. Be warm, friendly, and human — this is a real phone conversation, not a form.
   Use a relaxed, empathetic tone (e.g. "Sure, happy to help with that", "No worries,
   let me check", "I hear you"). Avoid sounding robotic, overly formal, or scripted.
8. Actively listen: react to what the caller actually said before moving on. If their
   request is unclear, ambiguous, or missing details you need, ask a short, friendly
   clarifying question instead of guessing or giving a generic answer.
9. Use natural contractions ("I'll", "that's", "you're") and light conversational
   fillers where it feels human ("Got it", "Sure thing", "Let's see"). Never rush
   through multiple questions at once — take it one step at a time, like a real person
   would on a phone call."""


async def build_system_prompt(
    profile: AgentProfile,
    *,
    first_turn: bool = True,
    voice: bool = False,
    tenant_id: str = "default",
) -> str:
    """Async entry-point: loads company branding from DB cache then renders the prompt.

    Use this from async contexts (chat service, voice session).  It reads the
    operator's company name, tagline, greeting script and per-department
    persona overrides from the database so changes made in the Settings UI
    are reflected on the very next conversation turn.
    """
    from app.core.company import get_company_branding

    branding = await get_company_branding(tenant_id)
    dept_key = profile.department.value
    overrides = (branding.agent_overrides or {}).get(dept_key) or {}
    display_name_override = overrides.get("display_name") or None
    custom_dept_script = (overrides.get("script") or "").strip()

    return render_system_prompt(
        profile,
        first_turn=first_turn,
        voice=voice,
        company_name=branding.company_name,
        company_tagline=branding.company_tagline,
        greeting_script=custom_dept_script or branding.greeting_script,
        display_name_override=display_name_override,
    )


def render_system_prompt(
    profile: AgentProfile,
    *,
    first_turn: bool = True,
    voice: bool = False,
    company_name: str | None = None,
    company_tagline: str | None = None,
    greeting_script: str | None = None,
    display_name_override: str | None = None,
) -> str:
    """Synchronous render — prefer :func:`build_system_prompt` from async callers."""
    from app.core.config import settings

    company_name = company_name or settings.company_name or "AlgoWorkforce"
    company_tagline = company_tagline or settings.company_tagline or "Your AI-Powered Enterprise Workforce"
    capabilities = "\n".join(f"- {c}" for c in profile.capabilities) or "- (general)"
    mcp = ", ".join(profile.mcp_connectors) or "(none)"
    languages = ", ".join(profile.languages)
    display_name = display_name_override or profile.display_name or profile.agent_name

    custom_script = (greeting_script or settings.agent_greeting_script or "").strip()

    if first_turn:
        if custom_script:
            try:
                greeting_example = custom_script.format(
                    agent_name=display_name,
                    company_name=company_name,
                    department=profile.department.value,
                )
            except KeyError:
                greeting_example = custom_script
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
