from importlib.resources import files
import asyncio

from toad.agent_schema import Agent
from toad.paths import get_config


class AgentReadError(Exception):
    """Problem reading the agents."""


async def read_agents() -> dict[str, Agent]:
    """Read agent information from data/agents and <toad_config_path>/agents/

    Raises:
        AgentReadError: If the files could not be read.

    Returns:
        A mapping of identity on to Agent dict.
    """
    import tomllib

    def load_agent(file) -> Agent | None:
        """Load an agent from a TOML file, returning None if inactive."""
        with file.open("rb") as f:
            agent: Agent = tomllib.load(f)
            return agent if agent.get("active", True) else None

    def read_agents() -> dict[str, Agent]:
        """Read agent information.

        Loads built-in agents from data/agents, then custom agents from
        <toad_config_path>/agents/. Custom agents with the same identity
        will override built-in ones.

        Returns:
            Mapping of identity to agent dicts.
        """
        agents: dict[str, Agent] = {}

        def add_agent(agent: Agent) -> None:
            identity = agent.get("identity")
            if identity:
                agents[identity] = agent

        try:
            for file in files("toad.data").joinpath("agents").iterdir():
                if agent := load_agent(file):
                    add_agent(agent)

            custom_agents_dir = get_config() / "agents"
            if custom_agents_dir.exists():
                for file in custom_agents_dir.glob("*.toml"):
                    if agent := load_agent(file):
                        add_agent(agent)
        except Exception as error:
            raise AgentReadError(f"Failed to read agents; {error}")

        return agents

    return await asyncio.to_thread(read_agents)
