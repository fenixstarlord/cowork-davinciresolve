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

    # Sync VERSION into plugin.json using Python (avoids jq dependency)
    $Python = $null
    foreach ($cmd in @("py", "python")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { $Python = $found.Source; break }
    }

    if ($Python) {
        & $Python -c "import json; p='.claude-plugin/plugin.json'; d=json.load(open(p)); d['version']='$Version'; json.dump(d, open(p,'w'), indent=2)"
    } else {
        Write-Host "WARNING: Python not found — skipping version sync to plugin.json"
    }

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
        "commands"
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
    Write-Host "  Cowork > Add Plugin > Personal > + > Upload plugin"
} finally {
    Pop-Location
}
