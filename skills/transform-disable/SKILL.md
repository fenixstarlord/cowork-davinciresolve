---
name: transform-disable
description: Reset transforms on active timeline clips and set scaling to Scale to Fit
user-invocable: true
argument-hint: ""
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /transform-disable

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Reset all transform properties on every clip in the **active timeline** to their defaults and set scaling to "Scale to Fit". Original values are backed up in clip markers so they can be restored later with `/transform-enable`.

**Important:** This command only affects the currently active timeline. It does NOT modify clips in other timelines.

## Usage
/transform-disable

## How It Works
1. Use `get_project_info` to identify the active timeline — tell the user which timeline will be affected
2. **Save a project backup to the Desktop** before making any changes:
   - Use `run_resolve_code` to save the current project (`project_manager.SaveProject()`) and then export a `.drp` backup to the user's Desktop
   - Detect the OS to determine the Desktop path:
     - **Windows**: `os.path.join(os.environ["USERPROFILE"], "Desktop")`
     - **macOS**: `os.path.expanduser("~/Desktop")`
   - Export with: `project_manager.ExportProject(project.GetName(), os.path.join(desktop_path, f"{project.GetName()}_backup_{timestamp}.drp"))`
   - Use a timestamp format like `YYYYMMDD_HHMMSS` (from `datetime.datetime.now().strftime("%Y%m%d_%H%M%S")`)
   - Tell the user where the backup was saved
   - If the export fails, warn the user but continue with the transform operation
3. Use `run_resolve_code` to iterate all video tracks and clips in the active timeline:
   - Skip any clip where `GetProperty()` returns `None` (transitions like Cross Dissolve, Smooth Cut)
   - For each media clip, read current transform + scaling values via `GetProperty()`
   - Get the clip's source start frame via `GetSourceStartFrame()` — this is the in-point in the source media and is unique per timeline instance even when the same media pool clip is used multiple times
   - Store original values as JSON in a Purple marker's `customData` field (marker name: `"TransformBackup"`, placed at the source start frame of the clip)
   - If a `TransformBackup` marker already exists at that source start frame, skip backing up that clip (it was already processed) and warn the user
   - Reset transform properties to defaults: Pan=0, Tilt=0, ZoomX=1, ZoomY=1, ZoomGang=True, RotationAngle=0, AnchorPointX=0, AnchorPointY=0, Pitch=0, Yaw=0, FlipX=False, FlipY=False
   - Set Scaling to `resolve.SCALE_FIT`
4. Report how many clips were modified, how many were skipped (already processed), and how many transitions were ignored

## Examples
- `/transform-disable`
- `/transform-disable` — then later `/transform-enable` to undo

## Notes
- Properties to back up and reset: Pan, Tilt, ZoomX, ZoomY, ZoomGang, RotationAngle, AnchorPointX, AnchorPointY, Pitch, Yaw, FlipX, FlipY, Scaling
- Scaling uses named constants from the `resolve` object: `resolve.SCALE_USE_PROJECT`, `resolve.SCALE_CROP`, `resolve.SCALE_FIT`, `resolve.SCALE_FILL`, `resolve.SCALE_STRETCH`. This command sets Scaling to `resolve.SCALE_FIT`
- Backup is stored per timeline instance via `AddMarker(source_start_frame, "Purple", "TransformBackup", "", 1, json_data)` where `source_start_frame = clip.GetSourceStartFrame()`
- Use `GetMarkerByCustomData()` to check for existing backups — the customData must be a unique search key, so prefix the JSON with `"TransformBackup:"` for reliable lookup
- Iterate tracks with `timeline.GetTrackCount("video")` and `timeline.GetItemListInTrack("video", idx)` (1-based indexing)
- Always check if `GetItemListInTrack()` returns None before iterating
