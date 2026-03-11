# DaVinci Resolve — Claude Cowork Plugin

## Project Overview

Claude Cowork plugin that connects to DaVinci Resolve via a local MCP server. Execute API calls, create timelines, manage media, and render projects — all from Claude Desktop's Cowork mode.

## Architecture

```
Claude Desktop (Cowork) → MCP Server (stdio) → DaVinci Resolve Scripting API
```

- **MCP Server** (`mcp_server.py`): Python server using FastMCP SDK, stdio transport
- **Skills**: Domain knowledge (API docs, Fusion guide, scripting patterns) loaded on-demand
- **Commands**: Slash commands for common workflows (/create-timelines, /render, etc.)
- **Resources**: Full API docs available at `resolve://api-docs`, `resolve://fusion-docs`, `resolve://examples`

## Key Files

| File | Purpose |
|------|---------|
| `mcp_server.py` | MCP server — tools, resources, execution engine |
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.mcp.json` | MCP connector config (stdio transport) |
| `skills/` | Domain knowledge (API ref, Fusion guide, scripting patterns) |
| `commands/` | Slash commands for common workflows |
| `CONNECTORS.md` | Documents the `~~resolve` connector |
| `docs/` | Raw API and Fusion documentation |
| `examples/examples.json` | Few-shot examples |

## MCP Tools

| Tool | Purpose |
|------|---------|
| `run_resolve_code` | Execute Python code in Resolve's scripting environment (persistent namespace) |
| `get_project_info` | Read-only project status check |
| `refresh_connection` | Re-connect to Resolve after project/timeline changes |

## Setup

```bash
./setup.sh                    # Install deps (just: mcp)
# Then add this folder as a plugin in Claude Desktop
```

## Coding Standards

- **Never print to stdout** in the MCP server — use stderr for logging
- Pre-loaded namespace: `resolve`, `project_manager`, `project`, `media_pool`, `timeline`
- Validate generated code against API method whitelist before execution
- No hallucinated API calls — use docs in `docs/` as source of truth
- 1-based indexing for timelines, tracks, and node indices
- Check for None before iterating (GetClipList, GetSubFolderList)

## Important Constraints

- **Resolve must be running** for tools to work
- **stdio transport** — server communicates via stdin/stdout (no network)
- **Persistent namespace** — variables carry across `run_resolve_code` calls within a session
- **30-second timeout** on code execution
