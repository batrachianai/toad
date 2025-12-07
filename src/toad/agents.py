from importlib.resources import files
import asyncio

from toad.agent_schema import Agent


class AgentReadError(Exception):
    """Problem reading the agents."""


async def read_agents() -> dict[str, Agent]:
    """Read agent information from data/agents

    Raises:
        AgentReadError: If the files could not be read.

    Returns:
        A mapping of identity on to Agent dict.
    """
    import tomllib

    def read_agents() -> list[Agent]:
        """Read agent information.

        Stored in data/agents

        Returns:
            List of agent dicts.
        """
        agents: list[Agent] = []
        try:
            for file in files("toad.data").joinpath("agents").iterdir():
                agent: Agent = tomllib.load(file.open("rb"))
                if agent.get("active", True):
                    agents.append(agent)

        except Exception as error:
            raise AgentReadError(f"Failed to read agents; {error}")

        return agents

    agents = await asyncio.to_thread(read_agents)
    agent_map = {agent["identity"]: agent for agent in agents}

    return agent_map
