#Requires -Version 5.1
<#
.SYNOPSIS
    Register (or uninstall) the DaVinci Resolve MCP server in Claude Desktop on Windows.
.PARAMETER Uninstall
    Remove the davinci-resolve server from Claude Desktop config.
#>
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$PluginDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopConfig = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"

# -- Find Python ---------------------------------------------------------------

function Find-Python {
    foreach ($cmd in @("py", "python")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    return $null
}

$Python = Find-Python
if (-not $Python) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ from https://python.org"
    exit 1
}

# -- Uninstall -----------------------------------------------------------------

if ($Uninstall) {
    Write-Host "=== Uninstalling DaVinci Resolve MCP Server ==="
    Write-Host ""

    if (-not (Test-Path $DesktopConfig)) {
        Write-Host "No Claude Desktop config found -- nothing to remove."
        exit 0
    }

    $pyCode = @"
import json, sys

config_path = sys.argv[1]

with open(config_path, "r") as f:
    try:
        config = json.load(f)
    except json.JSONDecodeError:
        print("Config file is empty or invalid -- nothing to remove.")
        sys.exit(0)

servers = config.get("mcpServers", {})
if "davinci-resolve" in servers:
    del servers["davinci-resolve"]
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print("Removed davinci-resolve from Claude Desktop config.")
    print("Restart Claude Desktop to apply.")
else:
    print("davinci-resolve server not found in config -- nothing to remove.")
"@

    & $Python -c $pyCode $DesktopConfig
    exit 0
}

# -- Install -------------------------------------------------------------------

Write-Host "=== DaVinci Resolve Cowork Plugin Setup ==="
Write-Host ""

# Check for uv
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "Installing uv (Python package runner)..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    Write-Host ""

    # Refresh PATH from registry so we can find the newly installed uv
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    $uv = Get-Command uv -ErrorAction SilentlyContinue
}

if (-not $uv) {
    Write-Host "ERROR: uv not found in PATH after install. Please install manually:"
    Write-Host "  powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
    exit 1
}

$UvPath = $uv.Source
Write-Host "Found uv at: $UvPath"

# Register MCP server in Claude Desktop config.
# Cowork plugins run inside a sandboxed VM, which can't reach the local
# Resolve scripting API. The MCP server must run natively on your PC via
# Claude Desktop's config so it can talk to Resolve directly.

Write-Host "Registering MCP server in Claude Desktop..."

$configDir = Split-Path -Parent $DesktopConfig
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
}
if (-not (Test-Path $DesktopConfig)) {
    Set-Content -Path $DesktopConfig -Value "{}"
}

$pyCode = @"
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
    "args": ["run", f"{plugin_dir}\\mcp_server.py"]
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"  Added davinci-resolve server -> {config_path}")
"@

& $Python -c $pyCode $DesktopConfig $PluginDir $UvPath

Write-Host ""
Write-Host "Setup complete!"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Run .\package.ps1 to create the plugin zip"
Write-Host "  2. In Claude Desktop: Cowork > Add Plugin > Personal > + > Upload plugin"
Write-Host "  3. Upload davinci-resolve.zip"
Write-Host "  4. Restart Claude Desktop (so the MCP server picks up)"
Write-Host "  5. Ensure DaVinci Resolve is running"
Write-Host "  6. Start a Cowork session and go!"
Write-Host ""
Write-Host "To uninstall:  .\setup.ps1 -Uninstall"
Write-Host ""
Write-Host "Available slash commands:"
Write-Host "  /create-timelines  - Create timelines from media pool clips"
Write-Host "  /render            - Set up and start render jobs"
Write-Host "  /import-media      - Import media files into the media pool"
Write-Host "  /project-info      - Show current project status"
Write-Host "  /explore           - Browse media pool, timelines, project structure"
