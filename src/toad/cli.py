import sys

import click
from toad.app import ToadApp
from toad.agent_schema import Agent


def set_process_title(title: str) -> None:
    """Set the process title.

    Args:
        title: Desired title.
    """
    try:
        import setproctitle

        setproctitle.setproctitle(title)
    except Exception:
        pass


def check_directory(path: str) -> None:
    """Check a path is directory, or exit the app.

    Args:
        path: Path to check.
    """
    from pathlib import Path

    if not Path(path).resolve().is_dir():
        print(f"Not a directory: {path}")
        sys.exit(-1)


async def get_agent_data(launch_agent) -> Agent | None:
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


def _read_default_agent() -> str:
    """Read the default_agent setting from toad.json if it exists."""
    import json
    from toad.paths import get_config

    try:
        settings_path = get_config() / "toad.json"
        if settings_path.exists():
            settings = json.loads(settings_path.read_text("utf-8"))
            return settings.get("agent", {}).get("default_agent", "")
    except Exception:
        pass
    return ""


class DefaultCommandGroup(click.Group):
    def parse_args(self, ctx, args):
        if "--help" in args or "-h" in args:
            return super().parse_args(ctx, args)
        if "--version" in args or "-v" in args:
            return super().parse_args(ctx, args)
        # Check if first arg is a known subcommand
        if not args or args[0] not in self.commands:
            # If not a subcommand, prepend the default command name
            args.insert(0, "run")
        return super().parse_args(ctx, args)

    def format_usage(self, ctx, formatter):
        formatter.write_usage(ctx.command_path, "[OPTIONS] PATH OR COMMAND [ARGS]...")


@click.group(cls=DefaultCommandGroup, invoke_without_command=True)
@click.option("-v", "--version", is_flag=True, help="Show version and exit.")
@click.pass_context
def main(ctx, version):
    """Canon TUI — AI for your terminal."""
    if version:
        from toad import get_version

        click.echo(get_version())
        ctx.exit()
    # If no command and no version flag, let the default command handling proceed
    if ctx.invoked_subcommand is None and not version:
        pass


# @click.group(invoke_without_command=True)
# @click.pass_context
@main.command("run")
@click.argument("project_dir", metavar="PATH", required=False, default=".")
@click.option(
    "-d",
    "--project-dir",
    "project_dir_option",
    metavar="PATH",
    default=None,
    help="Project directory (overrides positional PATH)",
)
@click.option("-a", "--agent", metavar="AGENT", default="")
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
@click.option(
    "--public-url",
    metavar="URL",
    default=None,
    help="Public URL to use in conjunction with --serve",
)
@click.option("-s", "--serve", is_flag=True, help="Serve Canon as a web application")
def run(
    port: int,
    host: str,
    serve: bool,
    project_dir: str = ".",
    project_dir_option: str | None = None,
    agent: str = "1",
    public_url: str | None = None,
):
    """Run an installed agent (same as `canon PATH`)."""

    if project_dir_option is not None:
        project_dir = project_dir_option
    check_directory(project_dir)

    # Check for saved default agent if none specified via CLI
    if not agent:
        agent = _read_default_agent()

    if agent:
        import asyncio

        agent_data = asyncio.run(get_agent_data(agent))
    else:
        agent_data = None

    app = ToadApp(
        mode=None if agent_data else "store",
        agent_data=agent_data,
        project_dir=project_dir,
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
            public_url=public_url,
        )
        set_process_title("canon --serve")
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
@click.option("-s", "--serve", is_flag=True, help="Serve Canon as a web application")
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
    identity = f"{command_name}.custom.canon.dega.org"

    agent_data: AgentData = {
        "identity": identity,
        "name": title or command.partition(" ")[0],
        "short_name": "agent",
        "url": "https://github.com/DEGAorg/canon-tui",
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
        set_process_title("canon acp --serve")
        server.serve()

    else:
        app = ToadApp(agent_data=agent_data, project_dir=project_dir)
        app.run()
        app.run_on_exit()

    print("")
    print("[bold magenta]Thanks for trying out Canon!")
    print("Please head to Discussions to share your experiences (good or bad).")
    print("https://github.com/DEGAorg/canon-tui/discussions")


@main.command("settings")
def settings() -> None:
    """Settings information."""
    app = ToadApp()
    print(f"{app.settings_path}")


@main.command("replay")
@click.argument("path", metavar="FILE")
def replay(path: str) -> None:
    """Replay interaction from a log file.

    This is a debugging aid. You probably won't need it unless you are building an agent.

    Run it in place of a command line to run an ACP agent:

    canon acp "canon replay canon.log"

    This will replay the agents output, and Canon will update the conversation as it would a real agent.
    """
    import time

    stdout = sys.stdout.buffer
    with open(path, "rb") as replay_file:
        for line in replay_file.readlines():
            sender, space, json_line = line.partition(b" ")
            if sender == b"[agent]":
                stdout.write(json_line.strip() + b"\n")
            time.sleep(0.01)
            stdout.write(line)
            stdout.flush()


@main.command("serve")
@click.option("-p", "--port", metavar="PORT", default=8000, type=int)
@click.option("-H", "--host", metavar="HOST", default="localhost")
@click.option(
    "--public-url",
    metavar="URL",
    default=None,
    help="Public URL for textual_serve Server (e.g. https://example.com)",
)
def serve(port: int, host: str, public_url: str | None = None) -> None:
    """Serve Canon as a web application."""
    from textual_serve.server import Server

    server = Server(
        sys.argv[0], host=host, port=port, title="Canon", public_url=public_url
    )
    set_process_title("canon serve")
    server.serve()


@main.command("about")
def about() -> None:
    """Show about information."""

    from toad import about

    app = ToadApp()

    print(about.render(app))


_CANON_GIT_URL = "git+https://github.com/DEGAorg/canon-tui.git"


@main.command("update")
@click.option(
    "--branch",
    default="main",
    show_default=True,
    help="Branch (or tag) to install from the canon-tui repo.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Print local + remote versions without installing.",
)
def update(branch: str, check: bool) -> None:
    """Update canon to the latest published build from GitHub."""
    import shutil
    import subprocess

    from toad import get_version

    local_version = get_version()

    if check:
        click.echo(f"Local:  canon-tui {local_version}")
        remote = _fetch_remote_version(branch)
        click.echo(
            f"Remote: canon-tui {remote} (branch={branch})"
            if remote
            else f"Remote: unknown (could not fetch pyproject.toml @ {branch})"
        )
        return

    if shutil.which("uv") is None:
        click.echo(
            "error: uv is not on PATH. Install uv first: "
            "curl -LsSf https://astral.sh/uv/install.sh | sh",
            err=True,
        )
        sys.exit(1)

    spec = f"canon-tui @ {_CANON_GIT_URL}@{branch}"
    click.echo(f"Updating from {branch} (local: {local_version})…")
    try:
        subprocess.run(
            ["uv", "tool", "install", spec, "--force", "--reinstall"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        click.echo(f"error: uv tool install failed (exit {exc.returncode})", err=True)
        sys.exit(exc.returncode)

    new_version = _read_installed_version()
    if new_version and new_version != local_version:
        click.echo(f"updated: {local_version} → {new_version}")
    elif new_version:
        click.echo(f"already up to date: {new_version}")
    else:
        click.echo("update complete (version check failed)")


def _fetch_remote_version(branch: str) -> str | None:
    """Best-effort read of the remote pyproject.toml version field."""
    import re
    import urllib.error
    import urllib.request

    url = (
        "https://raw.githubusercontent.com/DEGAorg/canon-tui/"
        f"{branch}/pyproject.toml"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', body, re.MULTILINE)
    return match.group(1) if match else None


def _read_installed_version() -> str | None:
    """Read the version of the canon-tui install that's currently on PATH."""
    import subprocess

    try:
        result = subprocess.run(
            ["canon", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    out = (result.stdout or "").strip() or (result.stderr or "").strip()
    return out or None


if __name__ == "__main__":
    main()
