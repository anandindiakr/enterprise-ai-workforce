"""Swarm orchestration: HierarchicalSwarm + universal SwarmRouter."""

from app.swarms.router import WorkforceRouter, workforce_router
from app.swarms.hierarchical import build_hierarchical_workforce

__all__ = ["WorkforceRouter", "workforce_router", "build_hierarchical_workforce"]
