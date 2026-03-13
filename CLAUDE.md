# DaVinci Resolve Plugin — Agent Instructions

## Architecture

```
Claude Desktop (Cowork) → MCP Server (stdio) → DaVinci Resolve Scripting API
```

- **MCP Server**: Python server using FastMCP SDK, stdio transport
- **Skills**: Domain knowledge (API docs, Fusion guide, scripting patterns) loaded on-demand
- **Resources**: Full API docs at `resolve://api-docs`, `resolve://fusion-docs`, `resolve://examples`

## MCP Tools

| Tool | Purpose |
|------|---------|
| `run_resolve_code` | Execute Python code in Resolve's scripting environment (persistent namespace) |
| `get_project_info` | Read-only project status check |
| `refresh_connection` | Re-connect to Resolve after project/timeline changes |

## Coding Standards

- **Never print to stdout** in the MCP server — use stderr for logging
- Pre-loaded namespace: `resolve`, `project_manager`, `project`, `media_pool`, `timeline`
- Validate generated code against API method whitelist before execution
- No hallucinated API calls — use docs in `docs/` as source of truth
- 1-based indexing for timelines, tracks, and node indices
- Check for None before iterating (GetClipList, GetSubFolderList)

## Important Constraints

- **Active timeline only** — all commands operate on the currently active timeline unless the user explicitly specifies otherwise. Never modify clips in other timelines without being asked.
- **Resolve must be running** for tools to work
- **stdio transport** — server communicates via stdin/stdout (no network)
- **Persistent namespace** — variables carry across `run_resolve_code` calls within a session
- **30-second timeout** on code execution
