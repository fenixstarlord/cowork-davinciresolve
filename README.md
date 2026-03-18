# DaVinci Resolve — Claude Cowork Plugin

Control DaVinci Resolve from Claude Desktop's Cowork mode. Execute API calls, create timelines, manage media, and render projects using natural language.

> **Disclaimer:** This software was vibe coded with reckless optimism and minimal understanding of what's actually happening under the hood. The developer (generous term) cannot guarantee that anything works, will continue to work, or ever worked in the first place. Use at your own risk, amusement, or horror. By the way, this disclaimer was AI-generated, because that's how not involved I am in this code.

## Prerequisites

- **[uv](https://docs.astral.sh/uv/)** — Python package runner (installs dependencies automatically)
- **Python 3.10+**
- **DaVinci Resolve** installed and running
- **Claude Desktop** (with Cowork mode)

If you don't have `uv`, install it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Installation

### Install via URL (Recommended)

1. Open **Claude Desktop** and switch to **Cowork** mode
2. Click **Add Plugin** > **Personal** > **+** (plus)
3. Select **Install from URL**
4. Paste: `https://github.com/fenixstarlord/cowork-davinciresolve`
5. The plugin installs automatically

### Install manually

1. **Build the plugin zip**

   **macOS / Linux:**

   ```bash
   git clone https://github.com/fenixstarlord/cowork-davinciresolve.git
   cd cowork-davinciresolve
   ./package.sh
   ```

   **Windows (PowerShell):**

   ```powershell
   git clone https://github.com/fenixstarlord/cowork-davinciresolve.git
   cd cowork-davinciresolve
   .\package.ps1
   ```

   This creates `davinci-resolve.zip`. No other setup needed — `uv` auto-installs the `mcp` dependency on first run.

2. **Upload to Claude Desktop**

   1. Open **Claude Desktop** and switch to **Cowork** mode
   2. Click **Add Plugin** > **Personal** > **+** (plus)
   3. Select **Upload plugin**
   4. Upload the `davinci-resolve.zip` file

### Start using it

1. Make sure **DaVinci Resolve** is running
2. Start a new Cowork session with the plugin enabled
3. Start asking Claude to do things in Resolve

### Custom Resolve script path

The plugin auto-detects the Resolve scripting modules path for your OS. If your installation is non-standard, edit `.mcp.json`:

```json
{
  "mcpServers": {
    "davinci-resolve": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "mcp_server.py"],
      "env": {
        "RESOLVE_SCRIPT_PATH": "/your/custom/path/to/Scripting/Modules"
      }
    }
  }
}
```

Default paths:
- **macOS**: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules`
- **Windows**: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules`
- **Linux**: `/opt/resolve/Developer/Scripting/Modules`

## Usage

Just describe what you want to do in natural language:

> "Show me all the timelines in this project"
>
> "Create a timeline for each clip in the FOOTAGE folder"
>
> "Render the current timeline as ProRes 422 HQ"
>
> "Import all .mov files from ~/Desktop/footage"

### Slash Commands

| Command | Description |
|---------|-------------|
| `/version` | Add custom named color versions to clips |
| `/version-up` | Auto-increment dated version numbers |
| `/transform-disable` | Disable transforms on timeline clips |
| `/transform-enable` | Re-enable transforms on timeline clips |

## How It Works

```
Claude Desktop (Cowork) ⟶ MCP Server (stdio or SSE) ⟶ DaVinci Resolve Scripting API
```

The plugin runs a local **MCP server** (`mcp_server.py`) that connects to Resolve's Python scripting API. Claude writes Python code, the server executes it in Resolve, and returns the results. A persistent namespace means variables carry across calls — enabling multi-step workflows.

### SSE Transport (Network Mode)

By default the server uses stdio transport. For remote clients, Windows compatibility, or cloud-hosted agents, you can run the server in SSE mode:

```bash
# Start the SSE server (default: 127.0.0.1:8765)
uv run mcp_server.py --transport sse

# Custom host/port
uv run mcp_server.py --transport sse --host 0.0.0.0 --port 9000

# Using environment variables
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=9000 uv run mcp_server.py
```

Then point your MCP client at `http://127.0.0.1:8765/sse`. The `.mcp.json` file includes a `davinci-resolve-sse` entry you can use directly.

### MCP Tools

| Tool | Description |
|------|-------------|
| `run_resolve_code` | Execute Python code in Resolve. Variables persist across calls. |
| `get_project_info` | Quick read-only project status (name, timelines, media pool, page). |
| `refresh_connection` | Re-connect after switching projects or if the connection drops. |

### Skills (domain knowledge)

The plugin includes skills that give Claude deep knowledge of Resolve's APIs:

- **resolve-api** — Full Resolve scripting API reference
- **fusion-scripting** — Fusion page scripting guide
- **resolve-scripting-guide** — Best practices, common patterns, gotchas

### Resources

Full documentation is also available as MCP resources:

- `resolve://api-docs` — Resolve API v20.3 documentation
- `resolve://fusion-docs` — Fusion scripting guide
- `resolve://examples` — Few-shot example patterns

## Troubleshooting

### "Not connected to DaVinci Resolve"
- Make sure Resolve is running **before** you start interacting
- Ask Claude to call `refresh_connection` to re-establish the connection

### "Could not import DaVinciResolveScript"
- Your Resolve scripting modules path doesn't match the default for your OS
- Set `RESOLVE_SCRIPT_PATH` in `.mcp.json` (see [Custom Resolve script path](#custom-resolve-script-path) above)

### MCP server not starting
- Confirm `uv` is installed: `uv --version`
- Confirm Python 3.10+ is available: `python3 --version` (or `py -3 --version` on Windows)
- Test the server manually: `uv run mcp_server.py` (from the plugin directory) — look for errors on stderr
- On Windows, if `uv` is not found after installing, restart your PowerShell session

### Connection drops mid-session
- Resolve may have been restarted or a new project was opened
- Ask Claude to call `refresh_connection`

## Project Structure

```
cowork-davinciresolve/
├── .claude-plugin/plugin.json    # Plugin manifest
├── .mcp.json                     # MCP server config (stdio + SSE)
├── mcp_server.py                 # MCP server — tools, resources, execution engine
├── skills/
│   ├── resolve-api/SKILL.md              # Resolve API reference
│   ├── fusion-scripting/SKILL.md         # Fusion scripting guide
│   ├── resolve-scripting-guide/SKILL.md  # Best practices & patterns
│   ├── version/SKILL.md                  # /version
│   ├── version-up/SKILL.md              # /version-up
│   ├── transform-disable/SKILL.md       # /transform-disable
│   └── transform-enable/SKILL.md        # /transform-enable
├── docs/                         # Raw API documentation
├── examples/examples.json        # Few-shot examples
├── setup.sh                      # Install script (macOS/Linux)
├── setup.ps1                     # Install script (Windows)
├── package.sh                    # Package script (macOS/Linux)
├── package.ps1                   # Package script (Windows)
├── CLAUDE.md                     # Claude Code project context
└── README.md
```

## License

MIT
