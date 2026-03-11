# DaVinci Resolve — Claude Cowork Plugin

Control DaVinci Resolve from Claude Desktop's Cowork mode. Execute API calls, create timelines, manage media, and render projects using natural language.

## Prerequisites

- Python 3.10+
- DaVinci Resolve (must be running)
- Claude Desktop with Cowork mode

## Installation

```bash
# Clone the repository
git clone https://github.com/fenixstarlord/resolvechat.git
cd resolvechat

# Run setup
./setup.sh
```

Then add the plugin to Claude Desktop:

1. Open **Claude Desktop**
2. Go to **Settings > Plugins > Install from folder**
3. Select this directory
4. Ensure DaVinci Resolve is running
5. Switch to **Cowork** mode

## Usage

Once the plugin is installed, Claude can interact with DaVinci Resolve directly. Just describe what you want to do:

- "Show me all the timelines in this project"
- "Create a timeline for each clip in the FOOTAGE folder"
- "Render the current timeline as ProRes 422 HQ"
- "Import all .mov files from ~/Desktop/footage"

### Slash Commands

| Command | Description |
|---------|-------------|
| `/create-timelines` | Create timelines from media pool clips |
| `/render` | Set up and start render jobs |
| `/import-media` | Import media files into the media pool |
| `/project-info` | Show current project status |
| `/explore` | Browse media pool, timelines, project structure |

## How It Works

The plugin runs a local MCP (Model Context Protocol) server that connects to DaVinci Resolve's scripting API. Claude sends Python code to the server, which executes it in Resolve and returns the results.

### MCP Tools

- **`run_resolve_code`** — Execute Python code in Resolve's scripting environment. Variables persist across calls.
- **`get_project_info`** — Quick read-only status check of the current project.
- **`refresh_connection`** — Re-connect after switching projects or if the connection drops.

## Troubleshooting

### "Not connected to DaVinci Resolve"
- Ensure DaVinci Resolve is running before starting Claude Desktop
- Try the `refresh_connection` tool to re-establish the connection

### "Could not import DaVinciResolveScript"
- The Resolve scripting modules path may not match your installation
- Set the `RESOLVE_SCRIPT_PATH` environment variable in `.mcp.json`:
  ```json
  "env": {
    "RESOLVE_SCRIPT_PATH": "/your/custom/path/to/Scripting/Modules"
  }
  ```

### Default script paths by OS
- **macOS**: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules`
- **Windows**: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules`
- **Linux**: `/opt/resolve/Developer/Scripting/Modules`

## License

MIT
