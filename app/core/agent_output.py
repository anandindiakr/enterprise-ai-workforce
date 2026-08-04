"""Shared utilities for cleaning raw Swarms agent.run()/SwarmRouter.run() output.

Swarms sometimes returns (or, under Hierarchical/multi-agent strategies,
*always* returns) the full internal conversation -- a list of
``{"role": ..., "content": ...}`` dicts, occasionally interleaved with raw
OpenAI tool-call objects -- instead of a single plain-text reply. If that
ever reaches the chat UI verbatim (or gets ``str()``-ed before cleaning),
the user sees things like::

    }', 'name': 'ModelMetaclass'}, 'id': 'call_...', 'type': 'function'}]},
    {'role': 'CustomerCareAgent', 'content': "..."}

``extract_agent_text`` is the single choke point responsible for turning
whatever Swarms handed back into the one clean natural-language reply that
should actually be shown to a human.
"""

from __future__ import annotations

import re
from typing import Any

_FUNC_RESULT_RE = re.compile(r"<\|function_results\|>.*?<\|end_function_results\|>", re.DOTALL)

# Tolerant matcher for a leaked Python-repr dict's 'role' + 'content' pair,
# captured together (not as two independent scans) so role/content stay
# aligned even when some dicts have content=None (e.g. tool-call entries)
# and therefore contribute no quoted-string match of their own.
_DICT_ROLE_CONTENT_RE = re.compile(
    r"""'role':\s*'(?P<role>[^']*)'\s*,\s*'content':\s*"""
    r"""(?:"(?P<dq>(?:[^"\\]|\\.)*)"|'(?P<sq>(?:[^'\\]|\\.)*)'|None)""",
    re.DOTALL,
)

_NON_REPLY_ROLES = {"user", "system", "tool", "function", "human"}


def _unescape_repr(text: str) -> str:
    """Undo Python-repr-style escaping left over from a str()'d dict."""
    if not text:
        return text
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    text = text.replace("\\'", "'").replace('\\"', '"')
    return text.strip()


def _extract_from_conversation_list(items: list[Any]) -> str:
    """Walk an actual (non-stringified) conversation list and return the
    last real assistant/agent message content, skipping user/tool turns."""
    for entry in reversed(items):
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role", "")).lower()
        content = entry.get("content")
        if role in _NON_REPLY_ROLES:
            continue
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def _extract_from_leaked_repr(raw: str) -> str:
    """Best-effort recovery when a conversation list/dict got str()'d
    upstream before we ever saw it as a real object. Pulls the last
    non-user/tool 'content' value out of the repr text, keeping each
    role/content pair aligned to the dict it actually came from."""
    matches = list(_DICT_ROLE_CONTENT_RE.finditer(raw))
    if not matches:
        return ""

    def _content_of(m: re.Match) -> str:
        dq, sq = m.group("dq"), m.group("sq")
        return _unescape_repr(dq if dq is not None else (sq or ""))

    for m in reversed(matches):
        role = (m.group("role") or "").lower()
        if role in _NON_REPLY_ROLES:
            continue
        content = _content_of(m)
        if content and "tool_calls" not in content and "ModelMetaclass" not in content:
            return content

    # Nothing clearly non-user found -- fall back to the very last content
    # block rather than showing the raw dump.
    return _content_of(matches[-1])


def extract_agent_text(raw: Any, task: str = "") -> str:
    """Return only the final natural-language assistant text.

    Accepts either the real object Swarms returned (``str``, ``list[dict]``,
    ``dict``) or an already-stringified version of it, and never lets raw
    conversation/tool-call bookkeeping reach the caller.
    """
    if raw is None:
        return ""

    # 0. Real (non-string) conversation object -- handle directly, no regex.
    if isinstance(raw, list):
        found = _extract_from_conversation_list(raw)
        return found or ""
    if isinstance(raw, dict):
        content = raw.get("content")
        return content.strip() if isinstance(content, str) else ""

    if not isinstance(raw, str):
        raw = str(raw)
    if not raw:
        return ""

    # 1. Strip task echo at the very start
    if task:
        stripped = raw.strip()
        task_stripped = task.strip()
        if stripped.startswith(task_stripped):
            raw = stripped[len(task_stripped):].lstrip("\n").strip()

    # 2. A leaked Python-repr conversation dump -- recover the real reply
    #    instead of showing the dump verbatim.
    if "'role':" in raw and "'content':" in raw:
        recovered = _extract_from_leaked_repr(raw)
        if recovered:
            return recovered

    # 3. Split on function-result blocks and keep what follows the last
    parts = _FUNC_RESULT_RE.split(raw)
    final = parts[-1].strip()

    if final:
        # Strip leading JSON array artefacts e.g. "[{\"tool\":...}]\n"
        final = re.sub(r"^\s*\[.*?\]\s*", "", final, flags=re.DOTALL).strip()
        if final:
            return final

    # 4. Fallback: strip Swarms reasoning-loop noise
    cleaned = re.sub(
        r"(Current Internal Reasoning Loop[^\n]*|Final Internal Reasoning Loop[^\n]*|None)\n?",
        "",
        raw,
    )
    return cleaned.strip()
