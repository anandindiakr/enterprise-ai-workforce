"""Shared utilities for cleaning raw Swarms agent.run() output."""

from __future__ import annotations

import re

_FUNC_RESULT_RE = re.compile(r"<\|function_results\|>.*?<\|end_function_results\|>", re.DOTALL)


def extract_agent_text(raw: str | None, task: str = "") -> str:
    """Return only the final assistant text from raw agent.run() output.

    Swarms' agent.run() sometimes echoes the task at the top, e.g.:
        "What is 2+2?\\nFour"
    We strip the task prefix and any tool-call bookkeeping noise.
    """
    if not raw:
        return ""

    # 1. Strip task echo at the very start
    if task:
        stripped = raw.strip()
        task_stripped = task.strip()
        if stripped.startswith(task_stripped):
            raw = stripped[len(task_stripped):].lstrip("\n").strip()

    # 2. Split on function-result blocks and keep what follows the last
    parts = _FUNC_RESULT_RE.split(raw)
    final = parts[-1].strip()

    if final:
        # Strip leading JSON array artefacts e.g. "[{\"tool\":...}]\n"
        final = re.sub(r"^\s*\[.*?\]\s*", "", final, flags=re.DOTALL).strip()
        if final:
            return final

    # 3. Fallback: strip Swarms reasoning-loop noise
    cleaned = re.sub(
        r"(Current Internal Reasoning Loop[^\n]*|Final Internal Reasoning Loop[^\n]*|None)\n?",
        "",
        raw,
    )
    return cleaned.strip()
