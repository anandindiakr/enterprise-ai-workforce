"""Hierarchical swarm: WorkforceDirector commands departmental agents."""

from __future__ import annotations

from swarms import Agent, HierarchicalSwarm

from app.agents.factory import build_all_department_agents, build_director_agent
from app.core.logging import logger


def build_hierarchical_workforce(*, max_loops: int = 1) -> HierarchicalSwarm:
    """Build the standard executive-led hierarchical swarm."""
    director: Agent = build_director_agent()
    workers = list(build_all_department_agents().values())

    swarm = HierarchicalSwarm(
        name="EnterpriseWorkforce",
        description=(
            "Executive director coordinating reception, customer care, sales, "
            "HR, finance, technology, and marketing agents."
        ),
        director=director,
        agents=workers,
        max_loops=max_loops,
        verbose=False,
    )
    logger.info("HierarchicalSwarm built with {} workers", len(workers))
    return swarm
