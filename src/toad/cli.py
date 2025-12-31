import sys

import click
from toad.app import ToadApp
from toad.agent_schema import Agent


def check_directory(path: str) -> None:
    """Check a path is directory, or exit the app.

    Args:
        path: Path to check.
    """
    from pathlib import Path

    if not Path(path).resolve().is_dir():
        print(f"Not a directory: {path}")
        sys.exit(-1)


async def get_agent_data(launch_agent: str) -> Agent | None:
    """Resolve a single agent name or identity to Agent data."""
    launch_agent = launch_agent.lower()

    from toad.agents import read_agents, AgentReadError

    try:
        agents = await read_agents()
    except AgentReadError:
        agents = {}

    for agent_data in agents.values():
        if (
            agent_data["short_name"].lower() == launch_agent
            or agent_data["identity"].lower() == launch_agent
        ):
            launch_agent = agent_data["identity"]
            break

    return agents.get(launch_agent)


async def get_agents_data(launch_agents: list[str]) -> list[Agent]:
    """Resolve multiple agent names or identities to Agent data."""
    from toad.agents import read_agents, AgentReadError

    try:
        agents = await read_agents()
    except AgentReadError:
        agents = {}

    result: list[Agent] = []
    seen_identities: set[str] = set()

    for launch_agent in launch_agents:
        launch_agent_lower = launch_agent.lower()
        selected: Agent | None = None

        for agent_data in agents.values():
            if (
                agent_data["short_name"].lower() == launch_agent_lower
                or agent_data["identity"].lower() == launch_agent_lower
            ):
                selected = agent_data
                break

        if selected is None:
            print(f"Unknown agent: {launch_agent}")
            continue

        identity = selected["identity"]
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        result.append(selected)

    return result


class DefaultCommandGroup(click.Group):
    def parse_args(self, ctx, args):
        if "--help" in args or "-h" in args:
            return super().parse_args(ctx, args)
        # Check if first arg is a known subcommand
        if not args or args[0] not in self.commands:
            # If not a subcommand, prepend the default command name
            args.insert(0, "run")
        return super().parse_args(ctx, args)

    def format_usage(self, ctx, formatter):
        formatter.write_usage(ctx.command_path, "[OPTIONS] PATH OR COMMAND [ARGS]...")


@click.group(cls=DefaultCommandGroup)
def main():
    """🐸 Toad — AI for your terminal."""


# @click.group(invoke_without_command=True)
# @click.pass_context
@main.command("run")
@click.argument("project_dir", metavar="PATH", required=False, default=".")
@click.option(
    "-a",
    "--agent",
    metavar="AGENT",
    default="",
    help="Agent to run (short name or identity). Use a comma-separated list for multiple agents.",
)
@click.option(
    "-p",
    "--port",
    metavar="PORT",
    default=8000,
    type=int,
    help="Port to use in conjunction with --serve",
)
@click.option(
    "-H",
    "--host",
    metavar="HOST",
    default="localhost",
    type=str,
    help="Host to use in conjunction with --serve",
)
@click.option("-s", "--serve", is_flag=True, help="Serve Toad as a web application")
def run(port: int, host: str, serve: bool, project_dir: str = ".", agent: str = ""):
    """Run an installed agent (same as `toad PATH`)."""

    check_directory(project_dir)

    agent_data: Agent | None = None
    agents_data: list[Agent] | None = None

    if agent:
        import asyncio

        agent_names = [name.strip() for name in agent.split(",") if name.strip()]
        if len(agent_names) == 1:
            agent_data = asyncio.run(get_agent_data(agent_names[0]))
        else:
            agents_data = asyncio.run(get_agents_data(agent_names))
            if not agents_data:
                print("No valid agents found for multi-agent mode.")
                sys.exit(-1)

    app = ToadApp(
        mode=None if (agent_data or agents_data) else "store",
        agent_data=agent_data,
        project_dir=project_dir,
        agents_data=agents_data,
    )
    if serve:
        import shlex
        from textual_serve.server import Server

        command_args = sys.argv
        # Remove serve flag from args (could be either --serve or -s)
        for flag in ["--serve", "-s"]:
            try:
                command_args.remove(flag)
                break
            except ValueError:
                pass
        serve_command = shlex.join(command_args)
        server = Server(
            serve_command,
            host=host,
            port=port,
            title=serve_command,
        )
        server.serve()
    else:
        app.run()
    app.run_on_exit()


@main.command("acp")
@click.argument("command", metavar="COMMAND")
@click.argument("project_dir", metavar="PATH", default=None)
@click.option(
    "-t",
    "--title",
    metavar="TITLE",
    help="Optional title to display in the status bar",
    default=None,
)
@click.option("-d", "--project-dir", metavar="PATH", default=None)
@click.option(
    "-p",
    "--port",
    metavar="PORT",
    default=8000,
    type=int,
    help="Port to use in conjunction with --serve",
)
@click.option(
    "-H",
    "--host",
    metavar="HOST",
    default="localhost",
    help="Host to use in conjunction with --serve",
)
@click.option("-s", "--serve", is_flag=True, help="Serve Toad as a web application")
def acp(
    command: str,
    host: str,
    port: int,
    title: str | None,
    project_dir: str | None,
    serve: bool = False,
) -> None:
    """Run an ACP agent from a command."""

    from rich import print

    from toad.agent_schema import Agent as AgentData

    command_name = command.split(" ", 1)[0].lower()
    identity = f"{command_name}.custom.batrachian.ai"

    agent_data: AgentData = {
        "identity": identity,
        "name": title or command.partition(" ")[0],
        "short_name": "agent",
        "url": "https://github.com/batrachianai/toad",
        "protocol": "acp",
        "type": "coding",
        "author_name": "Will McGugan",
        "author_url": "https://willmcgugan.github.io/",
        "publisher_name": "Will McGugan",
        "publisher_url": "https://willmcgugan.github.io/",
        "description": "Agent launched from CLI",
        "tags": [],
        "help": "",
        "run_command": {"*": command},
        "actions": {},
    }
    if serve:
        import shlex
        from textual_serve.server import Server

        command_components = [sys.argv[0], "acp", command]
        if project_dir:
            command_components.append(f"--project-dir={project_dir}")
        serve_command = shlex.join(command_components)

        server = Server(
            serve_command,
            host=host,
            port=port,
            title=serve_command,
        )
        server.serve()
    else:
        app = ToadApp(agent_data=agent_data, project_dir=project_dir)
        app.run()
        app.run_on_exit()

    print("")
    print("[bold magenta]Thanks for trying out Toad!")
    print("Please head to Discussions to share your experiences (good or bad).")
    print("https://github.com/batrachianai/toad/discussions")


@main.command("settings")
def settings() -> None:
    """Settings information."""
    app = ToadApp()
    print(f"{app.settings_path}")


# @main.command("replay")
# @click.argument("path", metavar="PATH.jsonl")
# def replay(path: str) -> None:
#     """Replay interaction from a jsonl file."""
#     import time

#     stdout = sys.stdout.buffer
#     with open(path, "rb") as replay_file:
#         for line in replay_file.readlines():
#             time.sleep(0.1)
#             stdout.write(line)
#             stdout.flush()


@main.command("serve")
@click.option("-p", "--port", metavar="PORT", default=8000, type=int)
@click.option("-H", "--host", metavar="HOST", default="localhost")
def serve(port: int, host: str) -> None:
    """Serve Toad as a web application."""
    from textual_serve.server import Server

    server = Server(sys.argv[0], host=host, port=port, title="Toad")
    server.serve()


@main.command("about")
def about() -> None:
    """Show about information."""

    from toad import about

    app = ToadApp()

    print(about.render(app))


if __name__ == "__main__":
    main()
