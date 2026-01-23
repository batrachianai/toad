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

## Video

Watch a preview of the Toad User Interface:

https://github.com/user-attachments/assets/ced36f4b-db02-4d29-8a0a-14ec64b22881

## Compatibility

Toad runs on Linux and macOS. Native Windows support is currently lacking (but on the roadmap), but Toad will run quite well with WSL.

Toad is a terminal application.
Any terminal will work, although if you are using the default terminal on macOS you will get a much reduced experience.
I recommend [Ghostty](https://ghostty.org/) which is fully featured and has amazing performance.

### Clipboard

On Linux, you may need to install `xclip` to enable clipboard support.

```
sudo apt install xclip
```

### Alternative shells

I'd like Toad to run multiple shells, but there are some compatibility issues I need to work out first, so for the moment the default is to use `/bin/sh`.

You can change the shell in settings. If you have any success, let me know.

## Getting Started

The easiest way to install Toad is by pasting the following in to your terminal:

```bash
curl -fsSL batrachian.ai/install | sh
```

If that doesn't work for any reason, then you can paste the following in to your terminal:

```bash
curl -LsSf uvx.sh/batrachian-toad/install.sh | sh
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

Or run without installing:

```bash
uvx --python 3.14 --from batrachian-toad toad
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

### Web server

You can run Toad as a web application.

Run the following, and click the link in the terminal:

```bash
toad serve
```

![textual-serve](https://github.com/user-attachments/assets/1d861d48-d30b-44cd-972d-5986a01360bf)

## Toad development

Toad was built by [Will McGugan](https://github.com/willmcgugan) and is currently under active development.

To discuss Toad, see the Discussions tab, or join the #toad channel on the [Textualize discord server](https://discord.gg/Enf6Z3qhVr).



### Roadmap

Some planned features:

- UI for MCP servers
- Expose model selection (waiting on ACP update)
- Sessions (resume)
- Multiple agents
- Windows native support
- Builtin editor
- Sidebar (widgets)
  - Git pending changes

### Reporting bugs

This project is trialling a non-traditional approach to issues.
Before an issue is created, there must be a post in Dicussions, approved by a Toad dev (Currently @willmcgugan).

By allowing the discussions to happen in the Discussion tabs, issues can be reserved for actionable tasks with a clear description and goal.















