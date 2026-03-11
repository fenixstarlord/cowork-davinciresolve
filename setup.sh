#!/bin/bash
set -e

echo "=== DaVinci Resolve Cowork Plugin Setup ==="
echo ""

# Install Python dependencies
echo "Installing dependencies..."
pip install mcp
echo ""

echo "Setup complete!"
echo ""
echo "To use this plugin in Claude Desktop:"
echo "  1. Open Claude Desktop"
echo "  2. Go to Settings > Plugins > Install from folder"
echo "  3. Select this directory: $(pwd)"
echo "  4. Ensure DaVinci Resolve is running"
echo "  5. Switch to Cowork mode and start using the plugin"
echo ""
echo "Available slash commands:"
echo "  /create-timelines  — Create timelines from media pool clips"
echo "  /render            — Set up and start render jobs"
echo "  /import-media      — Import media files into the media pool"
echo "  /project-info      — Show current project status"
echo "  /explore           — Browse media pool, timelines, project structure"
