# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-03-18

### Added
- SSE (Server-Sent Events) transport mode for remote and Windows clients (`--transport sse`)
- CLI flags for transport configuration: `--transport`, `--host`, `--port`
- Environment variable fallbacks: `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`
- SSE server entry in `.mcp.json` (`davinci-resolve-sse`)
- Security warning when binding to `0.0.0.0`
- `uvicorn` dependency for SSE transport

## [0.1.2] - 2026-03-17

### Fixed
- Auto-set `RESOLVE_SCRIPT_LIB` and `RESOLVE_SCRIPT_API` environment variables before importing DaVinciResolveScript, fixing connection failures on systems where these weren't configured globally

## [0.1.1] - 2026-03-17

### Fixed
- MCP server crash on startup caused by incompatible `version` kwarg passed to `FastMCP()` constructor (newer `mcp` package versions removed this parameter)
- Slash commands listed in setup scripts and README now match actual commands (`/version`, `/version-up`, `/transform-disable`, `/transform-enable`)

### Changed
- README now shows install-from-URL as the recommended installation method
- Updated project structure in README to match actual files
- Removed unused `__version__` variable from `mcp_server.py`

## [0.1.0] - 2025-06-13

### Added
- Lazy connection to DaVinci Resolve (connect on first tool call, not at startup)
- Auto-launch Resolve if not running when a tool is invoked
- Namespace helper utilities for the scripting environment
- `/version` command to add custom named color versions to clips
- `/version-up` command to auto-increment dated version numbers
- `/transform-enable` and `/transform-disable` commands

### Changed
- Renamed transform commands for clarity

## [0.0.3] - 2025-05-15

### Fixed
- Missing plugin commands by removing invalid manifest fields
- Registered slash commands in `plugin.json` so Cowork discovers them

### Changed
- Enforced active-timeline-only rule across all commands
- Added `allowed-tools` to all commands so MCP tools run without permission prompts
- Removed unnecessary confirmation prompts from transform commands
- Scoped disable/restore-transform to active timeline only

### Added
- Scaling included in backed-up transform properties
- Per-instance transform backup storage at source start frame
- Use `resolve.SCALE_FIT` constant instead of hardcoded integer

## [0.0.2] - 2025-04-20

### Added
- Refactored into Claude Cowork plugin with local MCP server
- Plugin packaging script (`package.sh`) and upload instructions
- `setup.sh` for zero-setup install via `uv`
- Disable-transform and restore-transform commands
- `install_url` and setup hook in plugin manifest
- Claude Desktop MCP config for Cowork sandbox

### Fixed
- MCP server not loading in Cowork sessions
- Full path to `uv` in Claude Desktop config

### Changed
- Removed legacy and redundant files from cowork plugin

## [0.0.1] - 2025-03-01

### Added
- Initial DaVinci Resolve chatbot with RAG-based document indexing
- Agentic assistant with individual API call execution
- Bootstrap `main.py` with auto-venv creation and dependency install
- API call validator against method whitelist
- Execute-all option and `/plan` mode toggle
- macOS and Windows Resolve script path auto-detection
- `CLAUDE.md`, skills, and agents for domain knowledge
