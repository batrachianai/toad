# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.5.9]: https://github.com/Textualize/textual/compare/v0.5.8...v0.5.9
[0.5.8]: https://github.com/Textualize/textual/compare/v0.5.7...v0.5.8
[0.5.7]: https://github.com/Textualize/textual/compare/v0.5.6...v0.5.7
[0.5.6]: https://github.com/Textualize/textual/compare/v0.5.5...v0.5.6
[0.5.5]: https://github.com/Textualize/textual/compare/v0.5.0...v0.5.5
[0.5.0]: https://github.com/batrachianai/toad/releases/tag/v0.5.0
