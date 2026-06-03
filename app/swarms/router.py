"""Universal :class:`SwarmRouter` for the AI Workforce platform.

This is the single entry point through which the rest of the system
dispatches a task. The router:

* selects an orchestration strategy based on the task and department
* assembles the right pool of Swarms ``Agent`` objects
* runs the swarm via :class:`swarms.SwarmRouter` (idiomatic Swarms usage)
* records telemetry and returns a :class:`WorkflowResult`
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from swarms import SwarmRouter

from app.agents.factory import (
    build_all_department_agents,
    build_department_agent,
    build_director_agent,
)
from app.core.exceptions import RoutingError
from app.core.logging import logger
from app.core.types import Department, SwarmStrategy
from app.models.schemas import WorkflowRequest, WorkflowResult
from app.telemetry.metrics import swarm_executions_total
from app.telemetry.tracing import span


# Heuristics for choosing a strategy when caller does not specify one.
_COMPLEXITY_KEYWORDS = {
    "analyze": SwarmStrategy.HIERARCHICAL,
    "report": SwarmStrategy.SEQUENTIAL,
    "compare": SwarmStrategy.MIXTURE,
    "decide": SwarmStrategy.MAJORITY_VOTING,
    "brainstorm": SwarmStrategy.GROUP_CHAT,
    "research": SwarmStrategy.SEQUENTIAL,
    "plan": SwarmStrategy.HIERARCHICAL,
    "draft": SwarmStrategy.SEQUENTIAL,
}


@dataclass(slots=True)
class _DispatchPlan:
    strategy: SwarmStrategy
    department: Department
    agents: list


class WorkforceRouter:
    """Front-door orchestration gateway."""

    def __init__(self) -> None:
        self._department_agents = None  # lazy

    # ------------------------------------------------------------------
    # Strategy / department resolution
    # ------------------------------------------------------------------

    def choose_strategy(
        self, task: str, department: Department | None
    ) -> SwarmStrategy:
        text = task.lower()
        for kw, strat in _COMPLEXITY_KEYWORDS.items():
            if kw in text:
                return strat
        # Cross-department or ambiguous tasks favor hierarchical control.
        if department in (None, Department.EXECUTIVE):
            return SwarmStrategy.HIERARCHICAL
        # Single-department conversational fallback: sequential single-agent.
        return SwarmStrategy.SEQUENTIAL

    def choose_department(self, task: str) -> Department:
        """Light-weight keyword router used when no department is provided."""
        text = task.lower()
        keyword_map: list[tuple[tuple[str, ...], Department]] = [
            (("invoice", "expense", "budget", "accounting", "finance"), Department.FINANCE),
            (("hire", "onboarding", "pto", "benefits", "hr"), Department.HR),
            (("crm", "lead", "demo", "deal", "sales", "pricing"), Department.SALES),
            (("bug", "outage", "vpn", "laptop", "password", "incident"), Department.TECHNOLOGY),
            (("campaign", "newsletter", "brand", "social", "marketing"), Department.MARKETING),
            (("ticket", "issue", "support", "help", "complain"), Department.CUSTOMER_CARE),
            (("appointment", "schedule", "reception", "visit"), Department.RECEPTION),
        ]
        for needles, dept in keyword_map:
            if any(n in text for n in needles):
                return dept
        return Department.RECEPTION

    # ------------------------------------------------------------------
    # Plan + execute
    # ------------------------------------------------------------------

    def _agents_for(self, plan_strategy: SwarmStrategy, department: Department) -> list:
        if self._department_agents is None:
            self._department_agents = build_all_department_agents()

        if plan_strategy == SwarmStrategy.HIERARCHICAL:
            director = build_director_agent()
            return [director, *self._department_agents.values()]

        # For everything else, single-department execution is the safe default.
        return [build_department_agent(department)]

    def plan(self, request: WorkflowRequest) -> _DispatchPlan:
        department = request.department or self.choose_department(request.task)
        strategy = request.strategy or self.choose_strategy(request.task, department)
        agents = self._agents_for(strategy, department)
        return _DispatchPlan(strategy=strategy, department=department, agents=agents)

    async def execute(self, request: WorkflowRequest) -> WorkflowResult:
        plan = self.plan(request)
        if not plan.agents:
            raise RoutingError("No agents available to handle request")

        with span(
            "swarm.execute",
            **{"swarm.strategy": plan.strategy.value, "swarm.department": plan.department.value},
        ):
            start = time.perf_counter()
            try:
                # Single-agent path: bypass SwarmRouter entirely.
                # SwarmRouter wraps SequentialWorkflow / AgentRearrange which require a
                # multi-agent "->" flow string -- that validation fails with one agent.
                if len(plan.agents) == 1:
                    agent = plan.agents[0]
                    output = await asyncio.to_thread(agent.run, request.task)
                else:
                    router = SwarmRouter(
                        name=f"workforce-{plan.department.value}",
                        description=f"Workforce dispatch for {plan.department.value}",
                        agents=plan.agents,
                        swarm_type=plan.strategy.value,
                        max_loops=1,
                    )
                    # Swarms `run` is sync; offload to a thread to keep API event loop snappy.
                    output = await asyncio.to_thread(router.run, request.task)

                duration_ms = int((time.perf_counter() - start) * 1000)
                swarm_executions_total.labels(plan.strategy.value, plan.department.value).inc()
                from app.core.agent_output import extract_agent_text
                clean_output = extract_agent_text(str(output) if output is not None else "", task=request.task)
                return WorkflowResult(
                    department=plan.department,
                    strategy=plan.strategy,
                    output=clean_output or str(output),
                    duration_ms=duration_ms,
                    agents_involved=[a.agent_name for a in plan.agents],
                    succeeded=True,
                )
            except Exception as exc:
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.exception("Swarm execution failed")
                return WorkflowResult(
                    department=plan.department,
                    strategy=plan.strategy,
                    output=None,
                    duration_ms=duration_ms,
                    agents_involved=[a.agent_name for a in plan.agents],
                    succeeded=False,
                    error=str(exc),
                )


_router: WorkforceRouter | None = None


def workforce_router() -> WorkforceRouter:
    global _router
    if _router is None:
        _router = WorkforceRouter()
    return _router


def reload_agents() -> None:
    """Invalidate cached agents (call after new API keys are saved)."""
    global _router
    if _router is not None:
        _router._department_agents = None
    logger.info("Agent cache cleared — will rebuild on next request.")
