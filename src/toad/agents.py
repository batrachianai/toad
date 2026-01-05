from dataclasses import dataclass, field
from importlib.resources import files
import asyncio
from pathlib import Path

from toad.agent_schema import Agent, ValidationError, validate_agent
from toad.paths import get_config


class AgentReadError(Exception):
    """Problem reading the agents."""


@dataclass
class AgentValidationError:
    """Represents a validation error for a custom agent."""

    file_path: Path
    error_message: str


@dataclass
class AgentReadResult:
    """Result of reading agents, including any validation errors."""

    agents: dict[str, Agent] = field(default_factory=dict)
    validation_errors: list[AgentValidationError] = field(default_factory=list)


async def read_agents() -> AgentReadResult:
    """Read agent information from data/agents and <toad_config_path>/agents/

    Raises:
        AgentReadError: If the built-in agents could not be read.

    Returns:
        AgentReadResult containing valid agents and any validation errors from custom agents.
    """
    import tomllib

    def load_agent(file, validate: bool = False) -> Agent | None:
        """Load an agent from a TOML file, returning None if inactive.

        Args:
            file: The file to load.
            validate: If True, validate against the Agent schema.

        Raises:
            ValidationError: If validation is enabled and fails.
        """
        with file.open("rb") as f:
            agent = tomllib.load(f)
            if not agent.get("active", True):
                return None
            if validate:
                return validate_agent(agent, file)
            return agent  # type: ignore[return-value]

    def read_agents() -> AgentReadResult:
        """Read agent information.

        Loads built-in agents from data/agents, then custom agents from
        <toad_config_path>/agents/. Custom agents with the same identity
        will override built-in ones.

        Returns:
            AgentReadResult with valid agents and validation errors.
        """
        result = AgentReadResult()

        def add_agent(agent: Agent) -> None:
            identity = agent.get("identity")
            if identity:
                result.agents[identity] = agent

        try:
            for file in files("toad.data").joinpath("agents").iterdir():
                if agent := load_agent(file):
                    add_agent(agent)
        except Exception as error:
            raise AgentReadError(f"Failed to read built-in agents; {error}")

        custom_agents_dir = get_config() / "agents"
        if custom_agents_dir.exists():
            for file in custom_agents_dir.glob("*.toml"):
                try:
                    if agent := load_agent(file, validate=True):
                        add_agent(agent)
                except ValidationError as error:
                    result.validation_errors.append(
                        AgentValidationError(
                            file_path=file,
                            error_message=str(error),
                        )
                    )
                except Exception as error:
                    result.validation_errors.append(
                        AgentValidationError(
                            file_path=file,
                            error_message=f"Failed to load agent: {error}",
                        )
                    )

        return result

    return await asyncio.to_thread(read_agents)
