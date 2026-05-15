"""Departmental and executive agent definitions (Swarms framework)."""

from app.agents.factory import (
    build_director_agent,
    build_department_agent,
    build_all_department_agents,
)

__all__ = [
    "build_director_agent",
    "build_department_agent",
    "build_all_department_agents",
]
