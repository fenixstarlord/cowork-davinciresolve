---
description: Restore previously backed-up transform values on all timeline clips
argument-hint: ""
---

# /restore-transform

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Restore original transform and scaling values on timeline clips that were previously modified by `/disable-transform`. Reads backup data from Purple clip markers and removes them after restoring.

## Usage
/restore-transform

## How It Works
1. Use `get_project_info` to confirm the current timeline
2. Use `run_resolve_code` to iterate all video tracks and clips:
   - For each clip, look for a marker named `"TransformBackup"` by scanning markers for the backup data prefix
   - Parse the stored JSON to recover original property values
   - Restore each transform property and Scaling via `SetProperty()`
   - Delete the backup marker after successful restore
3. Report how many clips were restored and how many had no backup

## Examples
- `/restore-transform`
- First run `/disable-transform`, then `/restore-transform` to undo

## Notes
- Reads backup from markers created by `/disable-transform` — marker color "Purple", name "TransformBackup"
- Properties restored: Pan, Tilt, ZoomX, ZoomY, ZoomGang, RotationAngle, AnchorPointX, AnchorPointY, Pitch, Yaw, FlipX, FlipY, Scaling
- The customData field is prefixed with `"TransformBackup:"` followed by JSON
- Use `GetMarkers()` to scan all markers on a clip — returns a dict keyed by frame ID
- Delete the backup marker with `DeleteMarkerAtFrame(frameId)` after restoring
- Iterate tracks with `timeline.GetTrackCount("video")` and `timeline.GetItemListInTrack("video", idx)` (1-based indexing)
- Always check if `GetItemListInTrack()` returns None before iterating
