---
name: snapshot
description: Save, restore, or compare project snapshots. Exports .drp backups to the Desktop.
user-invocable: true
argument-hint: "[save [<name>] | restore | restore timeline | diff <name1> <name2> | list]"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /snapshot

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Take a snapshot of the current project state (timeline structure, clip list, render settings), export a `.drp` project backup to the Desktop, and compare snapshots to see exactly what changed between sessions or editorial passes.

**Important:** The save subcommand exports a copy of the project to the Desktop but does not modify the project itself.

## Usage

```
/snapshot save [<name>]         — Save a full project snapshot and export .drp to Desktop
/snapshot restore               — Restore the full project from a snapshot (.drp import)
/snapshot restore timeline      — Restore only the active timeline's clips from a snapshot
/snapshot diff                   — Compare active timeline's current state to the most recent snapshot
/snapshot diff <name>            — Compare active timeline's current state to a specific snapshot
/snapshot list                  — List all saved snapshots
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

## Subcommand: restore

Restore the full project from a previously saved snapshot by importing the `.drp` backup.

### Step 1 — List snapshots with paginated picker

Show the last 10 snapshots (most recent first), numbered 1–9 and 0 (for the 10th). If there are more than 10, show `n` to load the next page.

```python
import os, json

snap_dir = os.path.expanduser("~/.resolve-snapshots")
project_dir = os.path.join(snap_dir, project.GetName().replace(" ", "_"))

if not os.path.exists(project_dir):
    print("No snapshots found for this project.")
else:
    files = sorted(
        [f for f in os.listdir(project_dir) if f.endswith(".json")],
        key=lambda f: os.path.getmtime(os.path.join(project_dir, f)),
        reverse=True
    )

    page = 0  # start at first page
    page_size = 10
    start = page * page_size
    page_files = files[start:start + page_size]

    for i, f in enumerate(page_files):
        key = i + 1 if i < 9 else 0  # 1-9, then 0 for 10th
        path = os.path.join(project_dir, f)
        with open(path) as fh:
            snap = json.load(fh)
        name = f.replace(".json", "")
        ts = snap.get("timestamp", "?")
        tl_count = len(snap.get("timelines", []))
        print(f"  {key}) {name} — {ts} — {tl_count} timelines")

    if len(files) > start + page_size:
        print(f"  n) Next page ({len(files) - start - page_size} more)")
```

Present this to the user and ask them to pick a number (1–9, 0) or `n` for the next page. If they pick `n`, increment the page and show the next 10.

### Step 2 — Import the .drp project backup

Once the user picks a snapshot, import the `.drp` file from the Desktop:

```python
import os

desktop = os.path.expanduser("~/Desktop")
export_dir = os.path.join(desktop, selected_snapshot_name)
drp_path = os.path.join(export_dir, f"{project.GetName()}.drp")

if not os.path.exists(drp_path):
    print(f"Project backup not found at: {drp_path}")
    print("The .drp file may have been moved or deleted from the Desktop.")
    print("You can manually import it via File > Import Project.")
else:
    result = project_manager.ImportProject(drp_path)
    if result:
        print(f"Project restored from: {drp_path}")
        print("The imported project appears as a separate entry in the Project Manager.")
        print("Switch to it via Project Manager if needed.")
    else:
        print(f"ImportProject returned False — the project name may already exist.")
        print("Try renaming the current project first, or import manually via File > Import Project.")
```

**Note:** `ImportProject` creates a new project entry in the Project Manager — it does not overwrite the current project. The user should switch to the imported project manually. Inform them of this.

Report to the user:

```
Restored from snapshot "<name>".
- Imported project: <drp_path>
- The restored project is available in the Project Manager.
- Switch to it to continue working from the restored state.
```

## Subcommand: restore timeline

Restore only the **active timeline** by comparing its current state to the snapshot and reverting clip properties (transforms, positions) to match the saved state.

### Step 1 — List snapshots with paginated picker

Same paginated picker as `restore` above — show last 10 snapshots numbered 1–9 and 0, with `n` for next page. Ask the user to pick one.

### Step 2 — Load the selected snapshot and find the matching timeline

```python
import os, json

snap_dir = os.path.expanduser("~/.resolve-snapshots")
project_dir = os.path.join(snap_dir, project.GetName().replace(" ", "_"))
snap_path = os.path.join(project_dir, f"{selected_snapshot_name}.json")

with open(snap_path) as f:
    snap = json.load(f)

active_tl = project.GetCurrentTimeline()
active_name = active_tl.GetName()

# Find matching timeline in snapshot
snap_tl = None
for tl_data in snap["timelines"]:
    if tl_data["name"] == active_name:
        snap_tl = tl_data
        break

if snap_tl is None:
    print(f"Timeline '{active_name}' not found in snapshot '{selected_snapshot_name}'.")
    print("Available timelines in this snapshot:")
    for tl_data in snap["timelines"]:
        print(f"  - {tl_data['name']}")
```

If the timeline isn't found, report available timelines and stop.

### Step 3 — Compare current clips against snapshot and restore transforms

Iterate the active timeline's clips and restore transform properties from the snapshot:

```python
restored = 0
not_found = 0
skipped_transitions = 0

video_tracks = active_tl.GetTrackCount("video")
for t in range(1, video_tracks + 1):
    items = active_tl.GetItemListInTrack("video", t)
    if items is None:
        continue
    for item in items:
        props = item.GetProperty()
        if props is None:
            skipped_transitions += 1
            continue

        clip_name = item.GetName()
        clip_start = item.GetStart()

        # Find matching clip in snapshot (by name, track, and track_type)
        match = None
        for sc in snap_tl["clips"]:
            if sc["name"] == clip_name and sc["track"] == t and sc["track_type"] == "video":
                match = sc
                break

        if match is None:
            not_found += 1
            continue

        # Restore transform properties
        for prop in ["ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle"]:
            if prop in match and match[prop] is not None:
                item.SetProperty(prop, match[prop])

        restored += 1

print(f"Restored transforms: {restored} clips")
print(f"Not found in snapshot: {not_found} clips")
print(f"Skipped transitions: {skipped_transitions}")
```

### Step 4 — Report results

```
## Timeline Restore: <active_name>

Restored from snapshot: <selected_snapshot_name>

- Clips restored: N (transforms reverted to snapshot state)
- Clips not found in snapshot: N (new clips added after snapshot)
- Transitions skipped: N

Restored properties: ZoomX, ZoomY, Pan, Tilt, RotationAngle
```

**Important:** `restore timeline` only restores transform properties on clips that exist in both the current timeline and the snapshot. It does **not** add or remove clips, change clip order, or modify edit points. It matches clips by name and track number. If clips have been renamed or moved to different tracks since the snapshot, they won't be matched.

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

Compare the **active timeline's current state** against a snapshot. Shows what changed (clips added/removed, duration changes, transform changes) since the snapshot was taken.

- `/snapshot diff` — compares against the **most recent** snapshot
- `/snapshot diff <name>` — compares against the named snapshot

### Step 1 — Load the snapshot

```python
import os, json

snap_dir = os.path.expanduser("~/.resolve-snapshots")
project_dir = os.path.join(snap_dir, project.GetName().replace(" ", "_"))

if not os.path.exists(project_dir):
    print("No snapshots found for this project.")
else:
    if snapshot_name:
        # User specified a snapshot name
        snap_path = os.path.join(project_dir, f"{snapshot_name}.json")
        if not os.path.exists(snap_path):
            print(f"Snapshot '{snapshot_name}' not found.")
            # List available snapshots
            files = [f.replace(".json", "") for f in os.listdir(project_dir) if f.endswith(".json")]
            print("Available: " + ", ".join(files))
    else:
        # No name given — use the most recent snapshot
        files = sorted(
            [f for f in os.listdir(project_dir) if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(project_dir, f)),
            reverse=True
        )
        if not files:
            print("No snapshots found.")
        else:
            snapshot_name = files[0].replace(".json", "")
            snap_path = os.path.join(project_dir, f"{snapshot_name}.json")
            print(f"Using most recent snapshot: {snapshot_name}")

    with open(snap_path) as f:
        snap = json.load(f)
```

### Step 2 — Find the active timeline in the snapshot

```python
active_tl = project.GetCurrentTimeline()
active_name = active_tl.GetName()

snap_tl = None
for tl_data in snap["timelines"]:
    if tl_data["name"] == active_name:
        snap_tl = tl_data
        break

if snap_tl is None:
    print(f"Timeline '{active_name}' not found in snapshot '{snapshot_name}'.")
    print("Available timelines in this snapshot:")
    for tl_data in snap["timelines"]:
        print(f"  - {tl_data['name']}")
```

If the timeline isn't found, report and stop.

### Step 3 — Capture current timeline state and compare

```python
# Capture current clips
current_clips = []
video_tracks = active_tl.GetTrackCount("video")
for t in range(1, video_tracks + 1):
    items = active_tl.GetItemListInTrack("video", t)
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
        for prop in ["ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle"]:
            clip[prop] = item.GetProperty(prop)
        current_clips.append(clip)

snap_clips = snap_tl["clips"]

# Build lookups by (name, track, track_type)
from collections import defaultdict

def build_lookup(clips):
    lookup = defaultdict(list)
    for c in clips:
        if c.get("track_type") == "video":
            key = (c["name"], c["track"], c["track_type"])
            lookup[key].append(c)
    return lookup

current_lookup = build_lookup(current_clips)
snap_lookup = build_lookup(snap_clips)

# Find added clips (in current but not in snapshot)
added = []
for key in current_lookup:
    if key not in snap_lookup:
        added.extend(current_lookup[key])

# Find removed clips (in snapshot but not in current)
removed = []
for key in snap_lookup:
    if key not in current_lookup:
        removed.extend(snap_lookup[key])

# Find modified clips — track both change descriptions and before/after data
modified = []
transform_changes = []  # for SVG visualization
for key in set(current_lookup.keys()) & set(snap_lookup.keys()):
    for cc in current_lookup[key]:
        for sc in snap_lookup[key]:
            changes = []
            has_transform = False
            if cc["start"] != sc["start"]:
                changes.append(f"start: {sc['start']} -> {cc['start']}")
            if cc["end"] != sc["end"]:
                changes.append(f"end: {sc['end']} -> {cc['end']}")
            if cc["duration"] != sc["duration"]:
                changes.append(f"duration: {sc['duration']} -> {cc['duration']}")
            for prop in ["ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle"]:
                if cc.get(prop) != sc.get(prop):
                    changes.append(f"{prop}: {sc.get(prop)} -> {cc.get(prop)}")
                    if prop in ("ZoomX", "ZoomY", "Pan", "Tilt"):
                        has_transform = True
            if changes:
                modified.append({"clip": cc["name"], "track": cc["track"], "changes": changes})
            if has_transform:
                transform_changes.append({"name": cc["name"], "before": sc, "after": cc})
            break  # match first occurrence

print(f"Added: {len(added)}, Removed: {len(removed)}, Modified: {len(modified)}")
print(f"Clips with transform changes: {len(transform_changes)}")
```

### Step 4 — Generate HTML diff report and attach it

Write a self-contained HTML file using the template at `tools/diff-visual.html` and attach it to the conversation. The template is zero-dependency (no CDN, no React) and renders a dark-themed dashboard with SVG viewport diagrams.

**How to use the template:**

1. Read the template file from `tools/diff-visual.html` in this repository.
2. Replace the `DATA` object in the `<script>` block with the actual diff results. The DATA shape is:

```js
const DATA = {
  snapshotName: "ColorSession_20260320",    // snapshot being compared
  timestamp: "2026-03-20T14:30:00",         // when the snapshot was taken
  timelineName: "Main Edit",                // active timeline name
  added: [
    { name: "NewClip.mov", track: 1, start: 100, duration: 50 },
  ],
  removed: [
    { name: "OldClip.mov", track: 2, start: 200, duration: 80 },
  ],
  transforms: [
    {
      name: "Interview_A.mov", track: 1,
      before: { ZoomX: 1.0, ZoomY: 1.0, Pan: 0, Tilt: 0 },
      after:  { ZoomX: 1.1, ZoomY: 1.1, Pan: -15, Tilt: 0 },
    },
  ],
};
```

3. Write the populated HTML to a temporary file (e.g. `/tmp/snapshot-diff-<name>.html`).
4. Attach the HTML file to the conversation so the user can click to view it.

Also include a brief text summary in the chat message:

```
## Snapshot Diff: <timeline_name> vs <snapshot_name>

- Added: N clips
- Removed: N clips
- Transform changes: N clips

See the attached visual report for details.
```

If nothing changed, skip the HTML attachment and just report:

> No differences found between the active timeline and snapshot "<name>".

**What the HTML dashboard shows:**

- **Header** with timeline name, snapshot name, and timestamp
- **Summary bar** with added/removed/modified counts
- **Transform cards** — one per clip with:
  - Track badge and clip name
  - SVG viewport diagram: blue dashed rect (snapshot), orange solid rect (current), yellow shift arrow, crosshairs
  - Change pills showing before → after values
- **Added/Removed tables** listing clips that were added or removed since the snapshot

## Implementation notes

- **Save is read-only**: `save` only reads project state and exports a backup — it never modifies the project.
- **Restore imports**: `restore` imports the `.drp` as a new project entry — it does not overwrite the current project.
- **Restore timeline modifies clips**: `restore timeline` writes transform properties back to clips on the active timeline. It does not add/remove clips or change edit points.
- **Paginated picker**: Both `restore` and `restore timeline` show the last 10 snapshots numbered 1–9 and 0, most recent first. `n` loads the next page.
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
/snapshot restore                 — pick a snapshot, import the .drp project backup
/snapshot restore timeline        — pick a snapshot, restore transforms on active timeline
/snapshot diff                   — compare active timeline clips against most recent snapshot
/snapshot diff ColorSession_20260320  — compare active timeline clips against a specific snapshot
/snapshot list
```
