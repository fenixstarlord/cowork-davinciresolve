#!/bin/bash
set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# ── Uninstall ─────────────────────────────────────────────────────────────
if [ "${1:-}" = "--uninstall" ]; then
    echo "=== Uninstalling DaVinci Resolve MCP Server ==="
    echo ""

    if [ ! -f "$DESKTOP_CONFIG" ]; then
        echo "No Claude Desktop config found — nothing to remove."
        exit 0
    fi

    python3 - "$DESKTOP_CONFIG" <<'PYEOF'
import json, sys

config_path = sys.argv[1]

with open(config_path, "r") as f:
    try:
        config = json.load(f)
    except json.JSONDecodeError:
        print("Config file is empty or invalid — nothing to remove.")
        sys.exit(0)

servers = config.get("mcpServers", {})
if "davinci-resolve" in servers:
    del servers["davinci-resolve"]
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print("Removed davinci-resolve from Claude Desktop config.")
    print("Restart Claude Desktop to apply.")
else:
    print("davinci-resolve server not found in config — nothing to remove.")
PYEOF
    exit 0
fi

# ── Install ───────────────────────────────────────────────────────────────
echo "=== DaVinci Resolve Cowork Plugin Setup ==="
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Installing uv (Python package runner)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
fi

# Resolve full path to uv — Claude Desktop launches with a minimal PATH
# that won't include Homebrew, cargo, or other user-installed locations.
UV_PATH="$(command -v uv)"
if [ -z "$UV_PATH" ]; then
    echo "ERROR: uv not found in PATH after install. Please install manually:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo "Found uv at: $UV_PATH"

# Register MCP server in Claude Desktop config.
# Cowork plugins run inside a sandboxed VM, which can't reach the local
# Resolve scripting API. The MCP server must run natively on your Mac via
# Claude Desktop's config so it can talk to Resolve directly.

echo "Registering MCP server in Claude Desktop..."

if [ ! -f "$DESKTOP_CONFIG" ]; then
    mkdir -p "$(dirname "$DESKTOP_CONFIG")"
    echo '{}' > "$DESKTOP_CONFIG"
fi

# Safely merge into the existing config (preserving other servers)
python3 - "$DESKTOP_CONFIG" "$PLUGIN_DIR" "$UV_PATH" <<'PYEOF'
import json, sys

config_path = sys.argv[1]
plugin_dir = sys.argv[2]
uv_path = sys.argv[3]

with open(config_path, "r") as f:
    try:
        config = json.load(f)
    except json.JSONDecodeError:
        config = {}

if "mcpServers" not in config:
    config["mcpServers"] = {}

config["mcpServers"]["davinci-resolve"] = {
    "command": uv_path,
    "args": ["run", f"{plugin_dir}/mcp_server.py"]
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"  Added davinci-resolve server -> {config_path}")
PYEOF

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run ./package.sh to create the plugin zip"
echo "  2. In Claude Desktop: Cowork > Add Plugin > Personal > + > Upload plugin"
echo "  3. Upload davinci-resolve.zip"
echo "  4. Restart Claude Desktop (so the MCP server picks up)"
echo "  5. Ensure DaVinci Resolve is running"
echo "  6. Start a Cowork session and go!"
echo ""
echo "To uninstall:  ./setup.sh --uninstall"
echo ""
echo "Available slash commands:"
echo "  /create-timelines  — Create timelines from media pool clips"
echo "  /render            — Set up and start render jobs"
echo "  /import-media      — Import media files into the media pool"
echo "  /project-info      — Show current project status"
echo "  /explore           — Browse media pool, timelines, project structure"
