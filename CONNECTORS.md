# Connectors

This plugin uses a local MCP server (`mcp_server.py`) to bridge Claude and DaVinci Resolve's scripting API.

## `~~resolve` — DaVinci Resolve MCP Server

**Transport:** stdio (launched automatically when the plugin is active)

### Tools

| Tool | Description |
|------|-------------|
| `run_resolve_code` | Execute Python code in Resolve's scripting environment. Persistent namespace with pre-loaded variables: `resolve`, `project_manager`, `project`, `media_pool`, `timeline`. |
| `get_project_info` | Quick read-only status check — returns project name, timeline info, media pool structure, and current page. |
| `refresh_connection` | Re-connect to Resolve and refresh the namespace. Use after switching projects or timelines. |

### Resources

| URI | Description |
|-----|-------------|
| `resolve://api-docs` | Full DaVinci Resolve scripting API reference |
| `resolve://fusion-docs` | Fusion scripting guide |
| `resolve://examples` | Few-shot examples for common tasks |

### Requirements

- **DaVinci Resolve must be running** on the same machine
- **uv** must be installed (`pip install uv` or `brew install uv`)
- The Resolve scripting modules must be accessible (auto-detected on macOS, Windows, and Linux)

### Troubleshooting

If the MCP tools are not available in your session:

1. **Check that Resolve is running** — the server connects on startup
2. **Check that `uv` is installed** — run `uv --version` in your terminal
3. **Restart the session** — plugin MCP servers start when the session begins
4. **Set `RESOLVE_SCRIPT_PATH`** if the scripting modules are in a non-default location
