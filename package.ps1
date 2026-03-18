#Requires -Version 5.1
<#
.SYNOPSIS
    Package the DaVinci Resolve Cowork plugin into a zip file for upload.
#>

$ErrorActionPreference = "Stop"

Write-Host "Packaging DaVinci Resolve Cowork plugin..."

$PluginDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $PluginDir

try {
    # Read VERSION
    $Version = (Get-Content -Path "VERSION" -Raw).Trim()
    Write-Host "Version: $Version"

    # Sync VERSION into plugin.json (use regex replace to preserve formatting)
    $pluginJsonPath = Join-Path ".claude-plugin" "plugin.json"
    $content = Get-Content -Path $pluginJsonPath -Raw
    $content = $content -replace '"version":\s*"[^"]*"', "`"version`": `"$Version`""
    [System.IO.File]::WriteAllText((Resolve-Path $pluginJsonPath).Path, $content)

    # Collect files to include (matching package.sh)
    $includeFiles = @(
        ".claude-plugin"
        ".mcp.json"
        "mcp_server.py"
        "VERSION"
        "CLAUDE.md"
        "CONNECTORS.md"
        "setup.sh"
        "setup.ps1"
        "package.ps1"
    )

    $includeDirs = @(
        "skills"
        "docs"
        "examples"
    )

    $excludePatterns = @("*.pyc", "__pycache__", ".DS_Store")

    # Build the list of items to zip
    $items = @()

    foreach ($f in $includeFiles) {
        $path = Join-Path $PluginDir $f
        if (Test-Path $path) { $items += $path }
    }

    foreach ($d in $includeDirs) {
        $path = Join-Path $PluginDir $d
        if (Test-Path $path) { $items += $path }
    }

    $zipPath = Join-Path $PluginDir "davinci-resolve.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

    Compress-Archive -Path $items -DestinationPath $zipPath -Force

    Write-Host ""
    Write-Host "Created: davinci-resolve.zip"
    Write-Host ""
    Write-Host "Upload this file in Claude Desktop:"
    Write-Host "  Cowork -> Add Plugin -> Personal -> + -> Upload plugin"
} finally {
    Pop-Location
}
