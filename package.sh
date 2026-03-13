#!/bin/bash
set -e

echo "Packaging DaVinci Resolve Cowork plugin..."

# Sync VERSION → plugin.json
VERSION=$(cat VERSION)
TMPFILE=$(mktemp)
jq --arg v "$VERSION" '.version = $v' .claude-plugin/plugin.json > "$TMPFILE" && mv "$TMPFILE" .claude-plugin/plugin.json
echo "Version: $VERSION"

zip -r davinci-resolve.zip \
    .claude-plugin \
    .mcp.json \
    mcp_server.py \
    VERSION \
    CLAUDE.md \
    skills/ \
    commands/ \
    docs/ \
    examples/ \
    CONNECTORS.md \
    setup.sh \
    -x "*.pyc" "__pycache__/*" ".DS_Store"

echo ""
echo "Created: davinci-resolve.zip"
echo ""
echo "Upload this file in Claude Desktop:"
echo "  Cowork > Add Plugin > Personal > + > Upload plugin"
