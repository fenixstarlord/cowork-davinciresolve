#!/bin/bash
set -e

echo "=== DaVinci Resolve Cowork Plugin Setup ==="
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Installing uv (Python package runner)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
fi

echo "Setup complete! Dependencies install automatically on first use via uv."
echo ""
echo "Next steps:"
echo "  1. Run ./package.sh to create the plugin zip"
echo "  2. In Claude Desktop: Cowork > Add Plugin > Personal > + > Upload plugin"
echo "  3. Upload davinci-resolve.zip"
echo "  4. Ensure DaVinci Resolve is running"
echo "  5. Start a Cowork session and go!"
echo ""
echo "Available slash commands:"
echo "  /create-timelines  — Create timelines from media pool clips"
echo "  /render            — Set up and start render jobs"
echo "  /import-media      — Import media files into the media pool"
echo "  /project-info      — Show current project status"
echo "  /explore           — Browse media pool, timelines, project structure"
