# Toad

A unified interface for AI in your terminal ([release announcement](https://willmcgugan.github.io/toad-released/)).

Run coding agents seamlessly under a single beautiful terminal UI, thanks to the [ACP](https://agentclientprotocol.com/protocol/initialization) protocol.

<table>

  <tbody>

  <tr>
    <td><img  alt="Screenshot 2025-10-23 at 08 58 58" src="https://github.com/user-attachments/assets/98387559-2e10-485a-8a7d-82cb00ed7622" /></td> 
    <td><img alt="Screenshot 2025-10-23 at 08 59 04" src="https://github.com/user-attachments/assets/d4231320-b678-47ba-99ce-02746ca2622b" /></td>    
  </tr>

  <tr>
    <td><img  alt="Screenshot 2025-10-23 at 08 59 22" src="https://github.com/user-attachments/assets/ddba550d-ff33-45ad-9f93-281187f5c974" /></td>
    <td><img  alt="Screenshot 2025-10-23 at 08 59 37" src="https://github.com/user-attachments/assets/e7943272-39a5-40a1-bedf-e440002e1290" /></td>
  </tr>
    
  </tbody>

  
</table>

## Compatibility

Toad runs on Linux and macOS. Native Windows support is currently lacking (but on the roadmap), but Toad will run quite well with WSL.

Toad is a terminal application.
Any terminal will work, although if you are using the default terminal on macOS you will get a much reduced experience.
I recommend [Ghostty](https://ghostty.org/) which is fully featured and has amazing performance.

## Clipboard

On Linux, you may need to install `xclip` to enable clipboard support.

```
sudo apt install xclip
```

## Getting Started

The easiest way to install Toad is by pasting the following in to your terminal:

```bash
curl -fsSL batrachian.ai/install | sh
```

You should now have `toad` installed.

If that doesn't work for any reason, then you can install with the following steps:

First [install UV](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then use UV to install toad:

```bash
uv tool install -U batrachian-toad --python 3.14
```

## Using Toad

Launch Toad with the following:

```bash
toad
```

You should see something like this:

<img alt="front-fs8" src="https://github.com/user-attachments/assets/8831f7de-5349-4b3f-9de9-d4565b513108" />

From this screen you will be able to find, install, and launch a coding agent.
If you already have an agent installed, you can skip the install step.
To launch an agent, select it and press space.

The footer will always display the most significant keys for the current context.
To see all the keys, summon the command palette with `ctrl+p` and search for "keys".

### Toad CLI

When running Toad, the current working directory is assumed to be your project directory.
To use another project directory, add the path to the command.
For example:

```bash
toad ~/projects/my-awesome-app
```

If you want to skip the initial agent screen, add the `-a` switch with the name of your chosen agent.
For example:

```bash
toad -a open-hands
```

To see all subcommands and switches, add the `--help` switch:

```bash
toad --help
```

### Multi-agent sessions

Toad can run multiple ACP agents concurrently in a single conversation.

You can start a multi-agent session from the CLI by passing a comma-separated list
of agents to `-a`:

```bash
toad -a open-hands,claude.com,goose.ai
```

- All listed agents are started in the same project directory.
- Prompts you type are broadcast to every agent.
- Responses and “thinking” streams are merged into a single conversation view.
- In multi-agent sessions, messages are prefixed with the agent name (for example `[OpenHands]`, `[Claude]`) so you can see who produced each output.

You can also launch multi-agent sessions from the Store screen:

- Press `T` on agents in any list (Launcher, Recommended, Coding agents, Chat & more) to add/remove them from a **team**.
- A status line below the launcher shows the current team members.
- Press `L` (on the Store screen) to launch a session with the selected team.
  - The first team member is treated as the primary agent for display.
  - The full team runs together as a multi-agent session.

### AI-managed “orchestrator” terminals

Agents running under ACP can request fully AI-managed terminals inside the
conversation. These are useful as dedicated workspaces for running commands,
tests, or other tools while keeping the main conversation focused on planning
and explanation.

Under the hood, this is powered by the ACP `terminal/*` tools. For agents that
are aware of Toad, a small helper tool is also available:

- `toad/create_orchestrator_terminal(sessionId, role, cwd, command, args, env)`  
  - `role` (optional): a free-form label such as `"worker"`, `"validator"`, etc.
  - `cwd` (optional): working directory for the terminal (defaults to the project root).
  - `command` (optional): executable to run. If omitted, Toad uses the current shell.
  - `args` (optional): list of arguments for the command.
  - `env` (optional): list of `{name, value}` environment variables to set.
  - Returns: `{"terminalId": "...", "role": "..."}`.

This allows an agent to spawn either a shell or another CLI client directly, for
example a tool-specific CLI that talks to a different model.

Once created, the orchestrator terminal is displayed in the conversation and can
be managed entirely by the AI via the standard ACP terminal tools:
`terminal/output`, `terminal/wait_for_exit`, `terminal/kill`, and
`terminal/release`. On the Toad side, these terminals integrate with the normal
terminal UX (for example, `ctrl+f` will focus the most recent non-finalized
terminal).bash
toad --help
```

### Web server

You can run Toad as a web application.

Run the following, and click the link in the terminal:

```bash
toad serve
```

![textual-serve](https://github.com/user-attachments/assets/1d861d48-d30b-44cd-972d-5986a01360bf)

### Sessions

Toad records per-project sessions that you can reopen later.

- User prompts, agent responses, and shell commands / output are stored under the project’s data directory.
- Use the **Sessions** panel in the sidebar to see recent sessions for the current project.
  - Open a session to restore its transcript into the conversation view.
  - Long sessions are automatically summarized; the summary is injected into your next agent turn so the model has compact context.
- Rename the current or most recent session with:

```text
/rename-session My current work
```

## Toad development

Toad was built by [Will McGugan](https://github.com/willmcgugan) and is currently under active development.

To discuss Toad, see the Discussions tab, or join the #toad channel on the [Textualize discord server](https://discord.gg/Enf6Z3qhVr).

### Roadmap
Some planned features:
- UI for MCP servers-P Expose model selection (waiting on ACP update)-C Richere)
- Sessions
- Richer multi-agent UI and coordination tools
- Windows native support

### Reporting bugs

This project is trialling a non-traditional approach to issues.
Before an issue is created, there must be a post in Dicussions, approved by a Toad dev (Currently @willmcgugan).

By allowing the discussions to happen in the Discussion tabs, issues can be reserved for actionable tasks with a clear description and goal.












