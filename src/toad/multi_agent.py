from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, List

from textual.content import Content

from toad import jsonrpc
from toad.agent import AgentBase
from toad.agent_schema import Agent as AgentData
from toad.acp.agent import Agent as AcpAgent


class MultiAgent(AgentBase):
    """An agent that fan-outs prompts to multiple underlying agents.

    MultiAgent presents a single AgentBase-compatible interface to Toad,
    while internally managing one ACP agent per configured AgentData.
    """

    def __init__(self, project_root: Path, agents: Iterable[AgentData]) -> None:
        super().__init__(project_root)
        self._agents_data: List[AgentData] = list(agents)
        self._agents: list[AcpAgent] = []

    @property
    def agents_data(self) -> list[AgentData]:
        return self._agents_data

    def get_info(self) -> Content:
        if not self._agents_data:
            return Content("")
        names = ", ".join(agent["name"] for agent in self._agents_data)
        return Content(names)

    def start(self, message_target) -> None:
        """Start all underlying agents."""
        self._agents.clear()
        for agent_data in self._agents_data:
            acp_agent = AcpAgent(self.project_root_path, agent_data)
            acp_agent.start(message_target)
            self._agents.append(acp_agent)

    async def send_prompt(self, prompt: str) -> str | None:
        """Send the same prompt to all underlying agents."""

        async def run_agent(acp_agent: AcpAgent) -> str | None:
            try:
                return await acp_agent.send_prompt(prompt)
            except jsonrpc.APIError:
                # Individual agent failures shouldn't abort the whole turn
                return None

        if not self._agents:
            return None

        results = await asyncio.gather(
            *(run_agent(agent) for agent in self._agents),
            return_exceptions=False,
        )

        for result in results:
            if isinstance(result, str) and result:
                return result
        return None

    async def set_mode(self, mode_id: str) -> str | None:
        """Set the same mode on all underlying agents, where supported."""
        errors: set[str] = set()
        for agent in self._agents:
            error = await agent.set_mode(mode_id)
            if error:
                errors.add(error)
        if errors:
            return "; ".join(sorted(errors))
        return None

    async def cancel(self) -> bool:
        """Request cancellation on all underlying agents."""
        if not self._agents:
            return False

        results = await asyncio.gather(
            *(agent.cancel() for agent in self._agents),
            return_exceptions=True,
        )
        cancelled = False
        for result in results:
            if isinstance(result, Exception):
                continue
            cancelled = cancelled or bool(result)
        return cancelled

    async def stop(self) -> None:
        """Gracefully stop all underlying agents."""
        await asyncio.gather(
            *(agent.stop() for agent in self._agents),
            return_exceptions=True,
        )