---
name: audit
description: Inspect the active timeline for common issues — gaps, mixed frame rates, empty tracks, transform problems, and more.
user-invocable: true
argument-hint: ""
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /audit

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Inspect the **active timeline** for common issues and generate a health report with actionable findings.

**Important:** This command is read-only. It does not modify the timeline.

## Usage

```
/audit
```

## Step 1 — Identify the active timeline and project settings

```python
tl = project.GetCurrentTimeline()
tl_name = tl.GetName()
tl_fps = tl.GetSetting("timelineFrameRate") or ""
tl_width = tl.GetSetting("timelineResolutionWidth") or ""
tl_height = tl.GetSetting("timelineResolutionHeight") or ""
video_tracks = tl.GetTrackCount("video")
audio_tracks = tl.GetTrackCount("audio")
tl_start = tl.GetStartFrame()
tl_end = tl.GetEndFrame()

print(f"Timeline: {tl_name}")
print(f"Resolution: {tl_width}x{tl_height} @ {tl_fps}fps")
print(f"Video tracks: {video_tracks}, Audio tracks: {audio_tracks}")
print(f"Range: {tl_start} - {tl_end}")
```

Tell the user which timeline is being audited.

## Step 2 — Collect all clip data

For each video and audio track, collect clip information:

```python
video_clips = {}  # track_num -> list of clip dicts
for t in range(1, video_tracks + 1):
    items = tl.GetItemListInTrack("video", t)
    track_clips = []
    if items:
        for item in items:
            props = item.GetProperty()
            if props is None:
                continue  # transition
            mp = item.GetMediaPoolItem()
            clip_info = {
                "name": item.GetName(),
                "start": item.GetStart(),
                "end": item.GetEnd(),
                "duration": item.GetDuration(),
                "source_start": item.GetSourceStartFrame() if hasattr(item, 'GetSourceStartFrame') else None,
                "source_end": item.GetSourceEndFrame() if hasattr(item, 'GetSourceEndFrame') else None,
                "track": t,
                "type": "video",
            }
            # Get media properties
            if mp:
                clip_info["file_path"] = mp.GetClipProperty("File Path") or ""
                clip_info["resolution"] = mp.GetClipProperty("Resolution") or ""
                clip_info["fps"] = mp.GetClipProperty("FPS") or ""
                clip_info["codec"] = mp.GetClipProperty("Video Codec") or ""
            else:
                clip_info["file_path"] = ""
                clip_info["resolution"] = ""
                clip_info["fps"] = ""
                clip_info["codec"] = ""

            # Get transform properties
            clip_info["zoom_x"] = item.GetProperty("ZoomX")
            clip_info["zoom_y"] = item.GetProperty("ZoomY")
            clip_info["pan"] = item.GetProperty("Pan")
            clip_info["tilt"] = item.GetProperty("Tilt")
            clip_info["rotation"] = item.GetProperty("RotationAngle")

            track_clips.append(clip_info)
    video_clips[t] = track_clips

# Do the same for audio tracks
audio_clips = {}
for t in range(1, audio_tracks + 1):
    items = tl.GetItemListInTrack("audio", t)
    track_clips = []
    if items:
        for item in items:
            props = item.GetProperty()
            if props is None:
                continue
            mp = item.GetMediaPoolItem()
            clip_info = {
                "name": item.GetName(),
                "start": item.GetStart(),
                "end": item.GetEnd(),
                "duration": item.GetDuration(),
                "track": t,
                "type": "audio",
                "file_path": mp.GetClipProperty("File Path") if mp else "",
            }
            track_clips.append(clip_info)
    audio_clips[t] = track_clips
```

**Important**: For timelines with many tracks or clips, break extraction into separate `run_resolve_code` calls per track to stay within the 30-second timeout.

## Step 3 — Run checks

Perform all checks and collect findings:

### Check 1: Gaps between clips (video track 1)

```python
gaps = []
for t, clips in video_clips.items():
    sorted_clips = sorted(clips, key=lambda c: c["start"])
    for i in range(1, len(sorted_clips)):
        prev_end = sorted_clips[i-1]["end"]
        curr_start = sorted_clips[i]["start"]
        if curr_start > prev_end:
            gap_frames = curr_start - prev_end
            gaps.append({
                "track": t,
                "after": sorted_clips[i-1]["name"],
                "before": sorted_clips[i]["name"],
                "at_frame": prev_end,
                "duration_frames": gap_frames,
            })
```

### Check 2: Mixed frame rates

```python
fps_mismatches = []
for t, clips in video_clips.items():
    for c in clips:
        if c["fps"] and c["fps"] != tl_fps:
            fps_mismatches.append({
                "clip": c["name"],
                "track": t,
                "clip_fps": c["fps"],
                "timeline_fps": tl_fps,
            })
```

### Check 3: Mixed resolutions

```python
resolution_mismatches = []
expected_res = f"{tl_width} x {tl_height}"
for t, clips in video_clips.items():
    for c in clips:
        if c["resolution"] and c["resolution"] != expected_res:
            resolution_mismatches.append({
                "clip": c["name"],
                "track": t,
                "clip_res": c["resolution"],
                "timeline_res": expected_res,
            })
```

### Check 4: Empty tracks

```python
empty_video = [t for t in range(1, video_tracks + 1) if not video_clips.get(t)]
empty_audio = [t for t in range(1, audio_tracks + 1) if not audio_clips.get(t)]
```

### Check 5: Clips with non-default transforms

```python
transformed = []
for t, clips in video_clips.items():
    for c in clips:
        is_transformed = (
            c.get("zoom_x") not in (None, 1.0) or
            c.get("zoom_y") not in (None, 1.0) or
            c.get("pan") not in (None, 0.0) or
            c.get("tilt") not in (None, 0.0) or
            c.get("rotation") not in (None, 0.0)
        )
        if is_transformed:
            transformed.append({
                "clip": c["name"],
                "track": t,
                "zoom": f"{c.get('zoom_x', '?')}x{c.get('zoom_y', '?')}",
                "pan": c.get("pan"),
                "tilt": c.get("tilt"),
                "rotation": c.get("rotation"),
            })
```

### Check 6: Offline media

```python
import os
offline = []
all_clips_flat = []
for t, clips in video_clips.items():
    all_clips_flat.extend(clips)
for t, clips in audio_clips.items():
    all_clips_flat.extend(clips)

for c in all_clips_flat:
    if c["file_path"] and not os.path.exists(c["file_path"]):
        offline.append({"clip": c["name"], "track": c["track"], "type": c["type"], "path": c["file_path"]})
```

## Step 4 — Present the audit report

```
## Timeline Audit: <tl_name>

**Resolution:** WxH @ FPS fps
**Tracks:** N video, M audio
**Duration:** start - end (N frames)

### Summary
| Check | Result |
|-------|--------|
| Gaps | N found |
| Frame rate mismatches | N clips |
| Resolution mismatches | N clips |
| Empty tracks | N video, M audio |
| Non-default transforms | N clips |
| Offline media | N clips |

### Gaps
| Track | After Clip | Before Clip | At Frame | Gap (frames) |
...

### Frame Rate Mismatches
| Clip | Track | Clip FPS | Timeline FPS |
...

(etc. for each check that has findings)

### Recommendations
- (actionable suggestions based on findings)
```

Only show sections with findings. If the timeline is clean, report:

> Timeline audit complete — no issues found.

Provide actionable recommendations based on findings. For example:
- Gaps: "Consider adding black slugs or extending adjacent clips"
- FPS mismatches: "Re-interpret clip frame rate or render before editing"
- Empty tracks: "Consider removing unused tracks to simplify the timeline"
- Transforms: "Run `/transform-disable` before roundtripping if transforms cause issues"

## Implementation notes

- **Read-only**: This command never modifies the timeline.
- **1-based indexing** for tracks.
- **Skip transitions**: `item.GetProperty()` returns `None` for transitions.
- **Guard against None**: `GetItemListInTrack()` can return None.
- **Persistent variables**: All collected data survives across `run_resolve_code` calls.
- **Large timelines**: Break extraction into per-track calls to avoid 30-second timeout.
- **Transform tolerance**: Consider very small floating-point deviations from defaults (e.g., 0.9999999 vs 1.0) as matching — use a tolerance of 0.001.
- **Offline check**: `os.path.exists()` checks from the machine running the MCP server, which should have the same filesystem access as Resolve.

## Examples

```
/audit
```
