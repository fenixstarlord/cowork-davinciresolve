---
description: Reset transforms on all timeline clips and set scaling to Scale to Fit
argument-hint: ""
---

# /disable-transform

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Reset all transform properties on every clip in the current timeline to their defaults and set scaling to "Scale to Fit". Original values are backed up in clip markers so they can be restored later with `/restore-transform`.

## Usage
/disable-transform

## How It Works
1. Use `get_project_info` to confirm the current timeline
2. Use `run_resolve_code` to iterate all video tracks and clips:
   - For each clip, read current transform + scaling values via `GetProperty()`
   - Store original values as JSON in a Purple marker's `customData` field (marker name: `"TransformBackup"`, placed at frame 1 of the clip)
   - If a `TransformBackup` marker already exists on a clip, skip backing up that clip (it was already processed) and warn the user
   - Reset transform properties to defaults: Pan=0, Tilt=0, ZoomX=1, ZoomY=1, ZoomGang=True, RotationAngle=0, AnchorPointX=0, AnchorPointY=0, Pitch=0, Yaw=0, FlipX=False, FlipY=False
   - Set Scaling to 2 (Scale to Fit)
3. Report how many clips were modified and how many were skipped

## Examples
- `/disable-transform`
- `/disable-transform` — then later `/restore-transform` to undo

## Notes
- Transform properties: Pan, Tilt, ZoomX, ZoomY, ZoomGang, RotationAngle, AnchorPointX, AnchorPointY, Pitch, Yaw, FlipX, FlipY
- Scaling value 2 = Scale to Fit (constants: 0=Project, 1=Crop, 2=Fit, 3=Fill, 4=Stretch)
- Backup is stored per-clip via `AddMarker(1, "Purple", "TransformBackup", "", 1, json_data)`
- Use `GetMarkerByCustomData()` to check for existing backups — the customData must be a unique search key, so prefix the JSON with `"TransformBackup:"` for reliable lookup
- Iterate tracks with `timeline.GetTrackCount("video")` and `timeline.GetItemListInTrack("video", idx)` (1-based indexing)
- Always check if `GetItemListInTrack()` returns None before iterating
