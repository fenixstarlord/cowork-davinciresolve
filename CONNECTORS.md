# Connectors

## How tool references work

This plugin uses `~~resolve` as a placeholder for the DaVinci Resolve MCP server.

## Connectors for this plugin

| Category | Placeholder | Server | Notes |
|----------|-------------|--------|-------|
| DaVinci Resolve | `~~resolve` | Local MCP server (`mcp_server.py`) | Requires Resolve running locally |

## Setup

1. Install the MCP server dependencies: `pip install mcp`
2. Ensure DaVinci Resolve is running
3. The plugin will auto-connect to Resolve via the local MCP server
