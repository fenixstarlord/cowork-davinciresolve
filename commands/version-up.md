---
description: Version up every grade on the active timeline with date and incrementing version number
argument-hint: ""
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /version-up

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Add a new local color version to every clip in the **active timeline** named `<YYMMDD>_v<NN>`. The version number increments globally across all dates — it finds the highest existing `_v<NN>` across all version names and adds 1.

**Important:** This command only affects the currently active timeline. It does NOT modify clips in other timelines.

## Usage
/version-up

## How It Works
1. Use `get_project_info` to identify the active timeline — tell the user which timeline will be affected
2. Use `run_resolve_code` to iterate all video tracks and clips in the active timeline:
   - Skip any clip where `GetProperty()` returns `None` (transitions)
   - For each media clip, scan existing local version names via `GetVersionNameList(0)` to find any matching the pattern `<YYMMDD>_v<NN>` (any date)
   - Track the highest `<NN>` found across all clips and all dates
3. After scanning all clips, determine the next version number: highest `<NN>` + 1 (zero-padded to 2 digits)
4. Iterate all clips again and add a new local color version via `AddVersion(versionName, 0)` where `versionName` is `<today's YYMMDD>_v<NN>`
5. Report how many clips were versioned and how many transitions were ignored

## Examples
- `/version-up` — first run creates `260311_v01` on all clips
- `/version-up` — second run creates `260311_v02` on all clips
- `/version-up` — run the next day creates `260312_v03` on all clips

## Notes
- Uses local versions (versionType `0`), not remote
- Date format is `YYMMDD` derived from today's date
- Version number `<NN>` is zero-padded to 2 digits and increments globally across all dates (not per-date)
- The highest `<NN>` is determined across all clips in the timeline to ensure consistency
- `AddVersion(name, 0)` creates and activates a new local version
- `GetVersionNameList(0)` returns all local version names for a clip
- Iterate tracks with `timeline.GetTrackCount("video")` and `timeline.GetItemListInTrack("video", idx)` (1-based indexing)
- Always check if `GetItemListInTrack()` returns None before iterating
