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

# -- Uninstall -----------------------------------------------------------------

if ($Uninstall) {
    Write-Host "=== Uninstalling DaVinci Resolve MCP Server ==="
    Write-Host ""

    if (-not (Test-Path $DesktopConfig)) {
        Write-Host "No Claude Desktop config found -- nothing to remove."
        exit 0
    }

    $raw = Get-Content -Raw $DesktopConfig
    try {
        $config = $raw | ConvertFrom-Json
    } catch {
        Write-Host "Config file is empty or invalid -- nothing to remove."
        exit 0
    }

    if ($config.mcpServers -and $config.mcpServers.PSObject.Properties["davinci-resolve"]) {
        $config.mcpServers.PSObject.Properties.Remove("davinci-resolve")
        $config | ConvertTo-Json -Depth 10 | Set-Content -Path $DesktopConfig
        Write-Host "Removed davinci-resolve from Claude Desktop config."
        Write-Host "Restart Claude Desktop to apply."
    } else {
        Write-Host "davinci-resolve server not found in config -- nothing to remove."
    }
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

$raw = Get-Content -Raw $DesktopConfig
try {
    $config = $raw | ConvertFrom-Json
} catch {
    $config = [PSCustomObject]@{}
}

if (-not $config.mcpServers) {
    $config | Add-Member -Type NoteProperty -Name mcpServers -Value ([PSCustomObject]@{})
}

$serverEntry = [PSCustomObject]@{
    command = $UvPath
    args = @("run", "$PluginDir\mcp_server.py")
}
$config.mcpServers | Add-Member -Type NoteProperty -Name "davinci-resolve" -Value $serverEntry -Force

$config | ConvertTo-Json -Depth 10 | Set-Content -Path $DesktopConfig
Write-Host "  Added davinci-resolve server -> $DesktopConfig"

Write-Host ""
Write-Host "Setup complete!"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart Claude Desktop (so the MCP server picks up)"
Write-Host "  2. Ensure DaVinci Resolve is running"
Write-Host "  3. Start a Cowork session and go!"
Write-Host ""
Write-Host "To uninstall:  .\setup.ps1 -Uninstall"
Write-Host ""
Write-Host "Available slash commands:"
Write-Host "  /version            - Add custom named color versions to clips"
Write-Host "  /version-up         - Auto-increment dated version numbers"
Write-Host "  /transform-disable  - Disable transforms on timeline clips"
Write-Host "  /transform-enable   - Re-enable transforms on timeline clips"
