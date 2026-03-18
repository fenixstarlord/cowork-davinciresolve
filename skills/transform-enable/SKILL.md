---
name: transform-enable
description: Restore previously backed-up transform values on active timeline clips
user-invocable: true
argument-hint: ""
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /transform-enable

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Restore original transform and scaling values on clips in the **active timeline** that were previously modified by `/transform-disable`. Reads backup data from Purple clip markers and removes them after restoring.

**Important:** This command only affects the currently active timeline. It does NOT modify clips in other timelines.

## Usage
/transform-enable

## How It Works
1. Use `get_project_info` to identify the active timeline — tell the user which timeline will be restored
2. Use `run_resolve_code` to iterate all video tracks and clips in the active timeline:
   - Skip any clip where `GetProperty()` returns `None` (transitions)
   - Get the clip's source start frame via `GetSourceStartFrame()` to identify the correct backup marker for this timeline instance
   - Look for a `"TransformBackup"` marker at that source start frame by scanning markers for the backup data prefix
   - Parse the stored JSON to recover original property values
   - Restore each transform property and Scaling via `SetProperty()`
   - Delete the backup marker after successful restore
3. Report how many clips were restored, how many had no backup, and how many transitions were ignored

## Examples
- `/transform-enable`
- First run `/transform-disable`, then `/transform-enable` to undo

## Notes
- Reads backup from markers created by `/transform-disable` — marker color "Purple", name "TransformBackup"
- Properties restored: Pan, Tilt, ZoomX, ZoomY, ZoomGang, RotationAngle, AnchorPointX, AnchorPointY, Pitch, Yaw, FlipX, FlipY, Scaling
- The customData field is prefixed with `"TransformBackup:"` followed by JSON
- Use `GetMarkers()` to scan all markers on a clip — returns a dict keyed by frame ID
- Delete the backup marker with `DeleteMarkerAtFrame(frameId)` after restoring
- Iterate tracks with `timeline.GetTrackCount("video")` and `timeline.GetItemListInTrack("video", idx)` (1-based indexing)
- Always check if `GetItemListInTrack()` returns None before iterating
