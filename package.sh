#!/bin/bash
set -e

echo "Packaging DaVinci Resolve Cowork plugin..."

zip -r davinci-resolve.zip \
    .claude-plugin \
    .mcp.json \
    mcp_server.py \
    CLAUDE.md \
    skills/ \
    commands/ \
    docs/ \
    examples/ \
    setup.sh \
    -x "*.pyc" "__pycache__/*" ".DS_Store"

echo ""
echo "Created: davinci-resolve.zip"
echo ""
echo "Upload this file in Claude Desktop:"
echo "  Cowork > Add Plugin > Personal > + > Upload plugin"
