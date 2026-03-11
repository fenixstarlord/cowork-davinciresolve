# Connectors

This plugin uses a local MCP server (`mcp_server.py`) to bridge Claude and DaVinci Resolve's scripting API.

## `~~resolve` — DaVinci Resolve MCP Server

**Transport:** stdio

### Why setup.sh is required

Cowork runs plugins inside a sandboxed Linux VM. The MCP server needs direct access to DaVinci Resolve's scripting API on your Mac — it can't reach Resolve from inside the sandbox.

Running `./setup.sh` registers the MCP server in Claude Desktop's **native** config (`~/Library/Application Support/Claude/claude_desktop_config.json`), so it launches on your Mac alongside Claude Desktop — outside the sandbox, where it can talk to Resolve.

The plugin itself (skills, commands, CLAUDE.md) still loads from the Cowork sandbox as normal.

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

### Setup

```bash
./setup.sh              # Register MCP server in Claude Desktop
./setup.sh --uninstall  # Remove MCP server from Claude Desktop
```

### Requirements

- **DaVinci Resolve must be running** on the same machine
- **uv** must be installed (`pip install uv` or `brew install uv`)
- The Resolve scripting modules must be accessible (auto-detected on macOS, Windows, and Linux)

### Troubleshooting

If the MCP tools are not available in your session:

1. **Run `./setup.sh`** — this registers the server in Claude Desktop's native config
2. **Restart Claude Desktop** — MCP servers only load on app startup
3. **Check that Resolve is running** — the server connects on startup
4. **Check that `uv` is installed** — run `uv --version` in your terminal
5. **Set `RESOLVE_SCRIPT_PATH`** env var if the scripting modules are in a non-default location
