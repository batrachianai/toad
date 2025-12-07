import sys

import click
from toad.app import ToadApp


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--project-dir", metavar="PATH", default=None)
def main(ctx, project_dir: str | None):
    """Toad. The Batrachian AI."""
    if ctx.invoked_subcommand is not None:
        return
    app = ToadApp(mode="store", project_dir=project_dir)
    app.run()


@main.command("acp")
@click.argument("command", metavar="COMMAND")
@click.option(
    "--title",
    metavar="TITLE",
    help="Optional title to display in the status bar",
    default=None,
)
@click.option("--project-dir", metavar="PATH", default=None)
@click.option(
    "--port",
    metavar="PORT",
    default=8000,
    type=int,
    help="Port to use in conjunction with --serve",
)
@click.option(
    "--host",
    metavar="HOST",
    default="localhost",
    help="Host to use in conjunction with --serve",
)
@click.option("--serve", is_flag=True, help="Serve Toad as a web application")
def acp(
    command: str,
    host: str,
    port: int,
    title: str | None,
    project_dir: str | None,
    serve: bool = False,
) -> None:
    """Run an ACP client."""

    from toad.agent_schema import Agent as AgentData

    agent_data: AgentData = {
        "identity": "toad.custom",
        "name": title or command.partition(" ")[0],
        "short_name": "agent",
        "url": "https://github.com/textualize/toad",
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
    app = ToadApp(agent_data=agent_data, project_dir=project_dir)
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
        app.run()

    from rich import print

    print("")
    print("[bold magenta]Thanks for trying out Toad!")
    print("Please head to Discussions to share your experiences (good or bad).")
    print("https://github.com/Textualize/toad/discussions")


@main.command("settings")
def settings() -> None:
    """Configure settings."""
    app = ToadApp()
    print(f"{app.settings_path}")


@main.command("replay")
@click.argument("path", metavar="PATH.jsonl")
def replay(path: str) -> None:
    """Replay interaction from a jsonl file."""
    import time

    stdout = sys.stdout.buffer
    with open(path, "rb") as replay_file:
        for line in replay_file.readlines():
            time.sleep(0.1)
            stdout.write(line)
            stdout.flush()


@main.command("serve")
@click.option("--port", metavar="PORT", default=8000, type=int)
@click.option("--host", metavar="HOST", default="localhost")
def serve(port: int, host: str) -> None:
    """Serve Toad as a web application."""
    from textual_serve.server import Server

    server = Server(sys.argv[0], host=host, port=port, title="Toad")
    server.serve()


if __name__ == "__main__":
    main()
