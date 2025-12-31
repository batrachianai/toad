# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.14] - 2025-

### Added

- Added optional os notifications
- Multi-agent sessions:
  - CLI support for launching multiple agents at once with `-a agent1,agent2,…`
  - Store screen support for selecting a team of agents and launching them together
- Agent-labelled output in multi-agent sessions (responses prefixed with agent name)
- ACP terminals are now focusable via the existing `ctrl+f` terminal focus key
- Toad-specific ACP helper tool `toad/create_orchestrator_terminal` for creating AI-managed “orchestrator” terminals, including support for running other CLIs (for example `kiro-cli`, `claude-code`) under AI control
- Persistent sessions:
  - Per-project session logs for user prompts, agent responses, and shell activity
  - Sessions sidebar panel for listing and reopening previous conversations
  - Automatic summarization and summary chaining for long sessions, injected into the next agent turn
  - `/rename-session <title>` slash command to name or rename sessions

### Changed

- Copy to clipboard will now use system APIs if available, in addition to OSC52

## [0.5.13] - 2025-12-29

### Changed

- Simplified diff visuals
- Fixed keys in permissions screen

### Fixed

- Fixed broken shell after running terminals

## [0.5.12] - 2025-12-28

### Fixed

- Fixed eroneous suggestion on buffered input 

## [0.5.11] - 2025-12-28

### Fixed

- Fixed tree picker when project path isn't cwd

## [0.5.10] - 2025-12-28

### Added

- Added a tree view to file picker

## [0.5.9] - 2025-12-27

### Changed

- Optimized directory scanning and filtering. Seems fast enough on sane sized repos. More work require for very large repos.
- Fixed empty tool calls with terminals

## [0.5.8] - 2025-12-26

### Fixed

- Fixed broken tool calls

## [0.5.7] - 2025-12-26

### Changes

- Cursor keys can navigate between sections in the store screen
- Optimized path search
- Disabled path search in shell mode
- Typing in the conversation view will auto-focus the prompt

### Added

- Added single character switches https://github.com/batrachianai/toad/pull/135

## [0.5.6] - 2025-12-24

### Fixed

- Fixed agent selector not focusing on run.
- Added project directory as second argument to `toad acp` rather than a switch.

## [0.5.5] - 2025-12-22

### Fixed

- Fixed column setting not taking effect

## [0.5.0] - 2025-12-18

### Added

- First release. This document will be updated for subsequent releases.

[0.5.12]: https://github.com/Textualize/textual/compare/v0.5.11...v0.5.12
[0.5.11]: https://github.com/Textualize/textual/compare/v0.5.10...v0.5.11
[0.5.10]: https://github.com/Textualize/textual/compare/v0.5.9...v0.5.10
[0.5.9]: https://github.com/Textualize/textual/compare/v0.5.8...v0.5.9
[0.5.8]: https://github.com/Textualize/textual/compare/v0.5.7...v0.5.8
[0.5.7]: https://github.com/Textualize/textual/compare/v0.5.6...v0.5.7
[0.5.6]: https://github.com/Textualize/textual/compare/v0.5.5...v0.5.6
[0.5.5]: https://github.com/Textualize/textual/compare/v0.5.0...v0.5.5
[0.5.0]: https://github.com/batrachianai/toad/releases/tag/v0.5.0
