---
description: Version up every grade on the active timeline with a custom name
disable-model-invocation: true
argument-hint: "<name>"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /version

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Add a new local color version to every clip in the **active timeline** using the provided name.

**Important:** This command only affects the currently active timeline. It does NOT modify clips in other timelines.

## Usage
/version <name>

## How It Works
1. Use `get_project_info` to identify the active timeline — tell the user which timeline will be affected
2. Use `run_resolve_code` to iterate all video tracks and clips in the active timeline:
   - Skip any clip where `GetProperty()` returns `None` (transitions)
   - Add a new local color version via `AddVersion(name, 0)` where `name` is the user-provided argument
   - The new version is automatically made active after `AddVersion`
3. Report how many clips were versioned and how many transitions were ignored

## Examples
- `/version hottoast` — creates version named `hottoast` on all clips
- `/version final_review` — creates version named `final_review` on all clips

## Notes
- Uses local versions (versionType `0`), not remote
- `AddVersion(name, 0)` creates and activates a new local version
- Iterate tracks with `timeline.GetTrackCount("video")` and `timeline.GetItemListInTrack("video", idx)` (1-based indexing)
- Always check if `GetItemListInTrack()` returns None before iterating
