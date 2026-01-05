# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- Settings screen will now expand to full width when the screen is < 100 characters
- Sidebar will float if focused and "hide sidebar when not in use" setting is True

### Fixed

- A more more defensive approach to watching directories, which may fixed stalling problem


## [0.5.20] - 2026-01-04

### Changed

- Smarter filesystem monitoring to avoid refreshes where nothing has changed

## [0.5.19] - 2026-01-04

### Added

- Added surfacing of "stop reason" from agents.
- Added `TOAD_LOG` env var (takes a path) to direct logs to a path.

## [0.5.18] - 2026-01-03

### Fixed

- Fixed footer setting

## [0.5.17] - 2026-01-03

### Fixed

- Fixed prompt settings not taking effect
- Fixed tool calls expanding but not updating the cursor

### Added

- Added atom-one-dark and atom-one-light themes

### Changed

- Allowed shell commands to be submitted prior to agent ready

## [0.5.15] - 2026-01-01

### Added

- Added pruning of very long conversations. This may be exposed in settings in the future.

### Fixed

- Fixed broken prompt with in question mode and the app blurs
- Fixed performance issue caused by timer

## [0.5.14] - 2025-12-31

### Added

- Added optional os notifications
- Added dialog to edit install commands

### Changed

- Copy to clipboard will now use system APIs if available, in addition to OSC52
- Implemented alternate approach to running the shell

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

[0.5.20]: https://github.com/batrachianai/toad/compare/v0.5.19...v0.5.20
[0.5.19]: https://github.com/batrachianai/toad/compare/v0.5.18...v0.5.19
[0.5.18]: https://github.com/batrachianai/toad/compare/v0.5.17...v0.5.18
[0.5.17]: https://github.com/batrachianai/toad/compare/v0.5.16...v0.5.17
[0.5.16]: https://github.com/batrachianai/toad/compare/v0.5.15...v0.5.16
[0.5.15]: https://github.com/batrachianai/toad/compare/v0.5.14...v0.5.15
[0.5.14]: https://github.com/batrachianai/toad/compare/v0.5.13...v0.5.14
[0.5.13]: https://github.com/batrachianai/toad/compare/v0.5.12...v0.5.13
[0.5.12]: https://github.com/batrachianai/toad/compare/v0.5.11...v0.5.12
[0.5.11]: https://github.com/batrachianai/toad/compare/v0.5.10...v0.5.11
[0.5.10]: https://github.com/batrachianai/toad/compare/v0.5.9...v0.5.10
[0.5.9]: https://github.com/batrachianai/toad/compare/v0.5.8...v0.5.9
[0.5.8]: https://github.com/batrachianai/toad/compare/v0.5.7...v0.5.8
[0.5.7]: https://github.com/batrachianai/toad/compare/v0.5.6...v0.5.7
[0.5.6]: https://github.com/batrachianai/toad/compare/v0.5.5...v0.5.6
[0.5.5]: https://github.com/batrachianai/toad/compare/v0.5.0...v0.5.5
[0.5.0]: https://github.com/batrachianai/toad/releases/tag/v0.5.0
