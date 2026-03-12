---
description: Import media files into the media pool
argument-hint: "<file paths or folder>"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /import-media

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Import media files or folders into the DaVinci Resolve media pool.

## Usage
/import-media $ARGUMENTS

## How It Works
1. Use ~~resolve to access the media storage and media pool
2. Import the specified files or folder contents
3. Optionally organize into a specific media pool folder
4. Report what was imported

## Examples
- `/import-media /Users/me/footage/*.mov`
- `/import-media ~/Desktop/project_files/ into a folder called RAW`
- `/import-media all .mp4 files from /Volumes/SSD/shoot_day_1`

## Notes
- Use `media_storage.AddItemListToMediaPool(paths)` for file paths
- Use `media_pool.ImportMedia(paths)` as an alternative
- Subfolders in the media pool can be created with `media_pool.AddSubFolder(parent, name)`
