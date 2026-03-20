---
name: snapshot
description: Take a snapshot of the current project state, export a project backup to the Desktop, or compare two snapshots to see what changed.
user-invocable: true
argument-hint: "[save [<name>] | diff <name1> <name2> | list]"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /snapshot

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Take a snapshot of the current project state (timeline structure, clip list, render settings), export a `.drp` project backup to the Desktop, and compare snapshots to see exactly what changed between sessions or editorial passes.

**Important:** The save subcommand exports a copy of the project to the Desktop but does not modify the project itself.

## Usage

```
/snapshot save [<name>]      — Save a snapshot and export project to Desktop (default name: Snapshot_YYYYMMDD)
/snapshot diff <name1> <name2>  — Compare two snapshots
/snapshot list               — List all saved snapshots
```

If no subcommand is given, default to `save`.

## Subcommand: save

### Step 1 — Generate snapshot name and capture project state

The snapshot name is `<name>_YYYYMMDD` — the date is always appended. If the user provides a name after `save`, use it as the prefix. Otherwise, default to `Snapshot`. Examples: `Snapshot_20260320`, `ColorSession_20260320`. If a snapshot with the same date-based name already exists, append the current time (`_HHMM`) to disambiguate: `ColorSession_20260320_1430`.

```python
import json
import os
from datetime import datetime

now = datetime.now()
date_str = now.strftime('%Y%m%d')
time_str = now.strftime('%H%M')

# Use user-provided name as prefix, or default to "Snapshot"
# user_name is the argument after "save", or None if not provided
prefix = user_name if user_name else "Snapshot"
snapshot_name = f"{prefix}_{date_str}"

# If a snapshot with this name already exists, append the time
snap_dir = os.path.expanduser("~/.resolve-snapshots")
project_dir = os.path.join(snap_dir, project.GetName().replace(" ", "_"))
if os.path.exists(project_dir):
    existing = [f.replace(".json", "") for f in os.listdir(project_dir) if f.endswith(".json")]
    if snapshot_name in existing:
        snapshot_name = f"{prefix}_{date_str}_{time_str}"

snapshot = {
    "timestamp": now.isoformat(),
    "snapshot_name": snapshot_name,
    "project_name": project.GetName(),
    "timelines": [],
    "media_pool": [],
    "render_settings": {},
}
```

### Step 2 — Capture all timelines

```python
tl_count = project.GetTimelineCount()
for i in range(1, tl_count + 1):
    tl = project.GetTimelineByIndex(i)
    tl_data = {
        "name": tl.GetName(),
        "index": i,
        "video_tracks": tl.GetTrackCount("video"),
        "audio_tracks": tl.GetTrackCount("audio"),
        "start_frame": tl.GetStartFrame(),
        "end_frame": tl.GetEndFrame(),
        "clips": [],
    }

    # Capture video clips
    for t in range(1, tl_data["video_tracks"] + 1):
        items = tl.GetItemListInTrack("video", t)
        if items is None:
            continue
        for item in items:
            props = item.GetProperty()
            if props is None:
                continue  # transition
            mp = item.GetMediaPoolItem()
            clip = {
                "name": item.GetName(),
                "track": t,
                "track_type": "video",
                "start": item.GetStart(),
                "end": item.GetEnd(),
                "duration": item.GetDuration(),
                "file_path": mp.GetClipProperty("File Path") if mp else "",
            }
            # Capture transform state
            for prop in ["ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle"]:
                clip[prop] = item.GetProperty(prop)
            tl_data["clips"].append(clip)

    # Capture audio clips
    for t in range(1, tl_data["audio_tracks"] + 1):
        items = tl.GetItemListInTrack("audio", t)
        if items is None:
            continue
        for item in items:
            props = item.GetProperty()
            if props is None:
                continue
            mp = item.GetMediaPoolItem()
            clip = {
                "name": item.GetName(),
                "track": t,
                "track_type": "audio",
                "start": item.GetStart(),
                "end": item.GetEnd(),
                "duration": item.GetDuration(),
                "file_path": mp.GetClipProperty("File Path") if mp else "",
            }
            tl_data["clips"].append(clip)

    snapshot["timelines"].append(tl_data)
```

**Important**: For projects with many timelines or large timelines, break capture into separate `run_resolve_code` calls per timeline to avoid the 30-second timeout.

### Step 3 — Capture media pool structure

```python
def scan_pool(folder, path=""):
    result = []
    name = folder.GetName()
    current_path = f"{path}/{name}" if path else name

    clips = folder.GetClipList()
    if clips:
        for clip in clips:
            result.append({
                "name": clip.GetName(),
                "bin": current_path,
                "file_path": clip.GetClipProperty("File Path") or "",
                "resolution": clip.GetClipProperty("Resolution") or "",
                "codec": clip.GetClipProperty("Video Codec") or "",
            })

    subfolders = folder.GetSubFolderList()
    if subfolders:
        for sf in subfolders:
            result.extend(scan_pool(sf, current_path))
    return result

snapshot["media_pool"] = scan_pool(media_pool.GetRootFolder())
```

### Step 4 — Save snapshot to disk

Save as JSON in a `.resolve-snapshots` directory under the user's home:

```python
import os, json

snap_dir = os.path.expanduser("~/.resolve-snapshots")
project_dir = os.path.join(snap_dir, project.GetName().replace(" ", "_"))
os.makedirs(project_dir, exist_ok=True)

snap_path = os.path.join(project_dir, f"{snapshot_name}.json")
with open(snap_path, "w") as f:
    json.dump(snapshot, f, indent=2)

clip_count = sum(len(tl["clips"]) for tl in snapshot["timelines"])
print(f"Saved: {snap_path}")
print(f"Timelines: {len(snapshot['timelines'])}")
print(f"Total clips: {clip_count}")
print(f"Media pool entries: {len(snapshot['media_pool'])}")
```

### Step 5 — Export project to Desktop

Export a `.drp` copy of the project to the user's Desktop, named with the snapshot name:

```python
import os

desktop = os.path.expanduser("~/Desktop")
export_dir = os.path.join(desktop, snapshot_name)
os.makedirs(export_dir, exist_ok=True)

export_path = os.path.join(export_dir, f"{project.GetName()}.drp")
result = project_manager.ExportProject(project.GetName(), export_path, withStillsAndLUTs=False)

if result:
    print(f"Project exported: {export_path}")
else:
    # ExportProject may not support the path argument in all versions
    # Fall back: export to the default location and notify the user
    print(f"ExportProject returned False — the project may have been exported to Resolve's default export location.")
    print(f"Target was: {export_path}")
```

**Note:** `project_manager.ExportProject()` behavior varies by Resolve version. The method signature is `ExportProject(projectName, filePath, withStillsAndLUTs=False)`. If the export fails, inform the user and suggest exporting manually via File > Export Project.

Report to the user:

```
Snapshot "<snapshot_name>" saved.
- Project: <project_name>
- Timelines: N
- Total timeline clips: N
- Media pool entries: N
- Snapshot JSON: <snap_path>
- Project export: <export_path>
```

## Subcommand: list

```python
import os, json

snap_dir = os.path.expanduser("~/.resolve-snapshots")
project_dir = os.path.join(snap_dir, project.GetName().replace(" ", "_"))

if not os.path.exists(project_dir):
    print("No snapshots found for this project.")
else:
    files = sorted(os.listdir(project_dir))
    for f in files:
        if f.endswith(".json"):
            path = os.path.join(project_dir, f)
            with open(path) as fh:
                snap = json.load(fh)
            name = f.replace(".json", "")
            ts = snap.get("timestamp", "?")
            tl_count = len(snap.get("timelines", []))
            print(f"{name} — {ts} — {tl_count} timelines")
```

Present as a table:

```
| Snapshot | Timestamp | Timelines |
|----------|-----------|-----------|
| before_edit | 2026-03-19T10:30:00 | 3 |
| after_edit | 2026-03-19T14:15:00 | 4 |
```

## Subcommand: diff

### Step 1 — Load both snapshots

```python
import os, json

snap_dir = os.path.expanduser("~/.resolve-snapshots")
project_dir = os.path.join(snap_dir, project.GetName().replace(" ", "_"))

with open(os.path.join(project_dir, f"{name1}.json")) as f:
    snap1 = json.load(f)
with open(os.path.join(project_dir, f"{name2}.json")) as f:
    snap2 = json.load(f)
```

### Step 2 — Compare timelines

```python
tl_names_1 = {tl["name"] for tl in snap1["timelines"]}
tl_names_2 = {tl["name"] for tl in snap2["timelines"]}

added_tl = tl_names_2 - tl_names_1
removed_tl = tl_names_1 - tl_names_2
common_tl = tl_names_1 & tl_names_2
```

### Step 3 — Compare clips in common timelines

For each common timeline, compare clip lists:

```python
diffs = {}
for tl_name in common_tl:
    tl1 = next(tl for tl in snap1["timelines"] if tl["name"] == tl_name)
    tl2 = next(tl for tl in snap2["timelines"] if tl["name"] == tl_name)

    clips1 = {(c["name"], c["track"], c["track_type"], c["start"]): c for c in tl1["clips"]}
    clips2 = {(c["name"], c["track"], c["track_type"], c["start"]): c for c in tl2["clips"]}

    keys1 = set(clips1.keys())
    keys2 = set(clips2.keys())

    added = keys2 - keys1
    removed = keys1 - keys2

    # Check for modified clips (same name+track but different properties)
    modified = []
    # Match by name+track+type (ignoring position)
    by_ntt_1 = {}
    for k, c in clips1.items():
        ntt = (c["name"], c["track"], c["track_type"])
        by_ntt_1.setdefault(ntt, []).append(c)
    by_ntt_2 = {}
    for k, c in clips2.items():
        ntt = (c["name"], c["track"], c["track_type"])
        by_ntt_2.setdefault(ntt, []).append(c)

    for ntt in set(by_ntt_1.keys()) & set(by_ntt_2.keys()):
        for c1 in by_ntt_1[ntt]:
            for c2 in by_ntt_2[ntt]:
                changes = []
                if c1["start"] != c2["start"]:
                    changes.append(f"start: {c1['start']} -> {c2['start']}")
                if c1["end"] != c2["end"]:
                    changes.append(f"end: {c1['end']} -> {c2['end']}")
                if c1["duration"] != c2["duration"]:
                    changes.append(f"duration: {c1['duration']} -> {c2['duration']}")
                for prop in ["ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle"]:
                    if c1.get(prop) != c2.get(prop):
                        changes.append(f"{prop}: {c1.get(prop)} -> {c2.get(prop)}")
                if changes:
                    modified.append({"clip": c1["name"], "track": c1["track"], "changes": changes})

    diffs[tl_name] = {
        "added": [clips2[k] for k in added],
        "removed": [clips1[k] for k in removed],
        "modified": modified,
        "track_count_change": {
            "video": tl2["video_tracks"] - tl1["video_tracks"],
            "audio": tl2["audio_tracks"] - tl1["audio_tracks"],
        }
    }
```

### Step 4 — Compare media pool

```python
pool1 = {(c["name"], c["file_path"]): c for c in snap1["media_pool"]}
pool2 = {(c["name"], c["file_path"]): c for c in snap2["media_pool"]}

added_media = set(pool2.keys()) - set(pool1.keys())
removed_media = set(pool1.keys()) - set(pool2.keys())
```

### Step 5 — Present diff report

```
## Snapshot Diff: <name1> vs <name2>

**<name1>**: <timestamp1>
**<name2>**: <timestamp2>

### Timeline Changes
- Added timelines: <list or "none">
- Removed timelines: <list or "none">

### <timeline_name>
| Change | Clip | Track | Details |
|--------|------|-------|---------|
| Added | clip_name | V1 | duration: 120 frames |
| Removed | clip_name | V2 | was at frame 1200 |
| Modified | clip_name | V1 | start: 100 -> 105, duration: 120 -> 115 |

### Media Pool Changes
- Added: N clips
- Removed: N clips
```

If there are no differences, report "Snapshots are identical."

## Implementation notes

- **Read-only**: Snapshots only read project state, never modify it.
- **1-based indexing** for tracks and timeline indices.
- **Skip transitions**: `item.GetProperty()` returns `None` for transitions.
- **Guard against None**: `GetItemListInTrack()`, `GetClipList()`, `GetSubFolderList()` can return None.
- **Persistent variables**: Snapshot data survives across `run_resolve_code` calls.
- **Large projects**: Break capture into per-timeline calls for projects with many timelines.
- **Storage**: Snapshots are saved as JSON files in `~/.resolve-snapshots/<ProjectName>/`. Each snapshot is typically a few KB to a few MB depending on project size.
- **Project export**: A `.drp` project file is exported to `~/Desktop/<snapshot_name>/`. This is a full Resolve project backup that can be re-imported.
- **Auto-naming**: Snapshot names are always `<prefix>_YYYYMMDD` (default prefix: `Snapshot`). If a same-day snapshot already exists, the time is appended: `<prefix>_YYYYMMDD_HHMM`.
- **ExportProject**: `project_manager.ExportProject(projectName, filePath, withStillsAndLUTs)` exports the project database entry. The `withStillsAndLUTs` flag controls whether stills and LUTs are included (default False to keep exports small).
- **Cross-session**: Snapshots persist on disk and can be compared across different sessions.

## Examples

```
/snapshot save                    — saves as Snapshot_20260320
/snapshot save ColorSession       — saves as ColorSession_20260320
/snapshot diff Snapshot_20260319 ColorSession_20260320
/snapshot list
```
