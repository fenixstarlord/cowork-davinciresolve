---
name: organize
description: Auto-organize media pool clips into bins by metadata — camera, date, resolution, codec, or filename pattern.
user-invocable: true
argument-hint: ""
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /organize

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Scan the media pool and auto-organize clips into bins based on configurable rules. Flags offline media, duplicate clips, and mismatched frame rates.

**Important:** This command creates new bins and moves clips within the media pool. It does not delete any clips or bins.

## Usage

```
/organize
```

## Step 0 — Ask for organization rules

Ask the user how they want clips organized:

> How should I organize your media pool? Pick a strategy:
>
> 1. **By camera** — group clips by Camera metadata (e.g., A-cam, B-cam)
> 2. **By date** — group by shooting date
> 3. **By resolution** — group by frame size (4K, HD, etc.)
> 4. **By codec** — group by video codec
> 5. **By file type** — group by extension (.mov, .mp4, .mxf, .wav, etc.)
> 6. **By filename pattern** — specify a regex to extract group names from filenames
> 7. **Custom** — combine multiple criteria

Also ask:

> Should I scan only the root folder, or all subfolders recursively?

Store the user's choices.

## Step 1 — Scan the media pool

Recursively scan the media pool to collect all clips and their metadata:

```python
def scan_folder(folder, path=""):
    clips = []
    folder_name = folder.GetName()
    current_path = f"{path}/{folder_name}" if path else folder_name

    clip_list = folder.GetClipList()
    if clip_list:
        for clip in clip_list:
            props = {}
            props["name"] = clip.GetName()
            props["file_path"] = clip.GetClipProperty("File Path") or ""
            props["resolution"] = clip.GetClipProperty("Resolution") or ""
            props["codec"] = clip.GetClipProperty("Video Codec") or ""
            props["fps"] = clip.GetClipProperty("FPS") or ""
            props["date"] = clip.GetClipProperty("Date Modified") or ""
            props["type"] = clip.GetClipProperty("Type") or ""
            props["duration"] = clip.GetClipProperty("Duration") or ""
            props["clip_obj"] = clip
            props["folder_obj"] = folder
            props["folder_path"] = current_path
            clips.append(props)

    subfolders = folder.GetSubFolderList()
    if subfolders:
        for sf in subfolders:
            clips.extend(scan_folder(sf, current_path))

    return clips

root = media_pool.GetRootFolder()
all_clips = scan_folder(root)
print(f"Found {len(all_clips)} clips")
```

**Important**: For large media pools (hundreds of clips), break the scan into separate `run_resolve_code` calls per top-level folder to avoid the 30-second timeout. Store results in the persistent namespace.

## Step 2 — Analyze and flag issues

Before organizing, scan for common problems:

```python
from collections import defaultdict
import os

# Check for offline media
offline = [c for c in all_clips if not c["file_path"] or not os.path.exists(c["file_path"])]

# Check for duplicates (same file path, different pool entries)
path_map = defaultdict(list)
for c in all_clips:
    if c["file_path"]:
        path_map[c["file_path"]].append(c)
duplicates = {p: clips for p, clips in path_map.items() if len(clips) > 1}

# Check for frame rate mismatches against project
project_fps = project.GetSetting("timelineFrameRate") or ""
mismatched_fps = [c for c in all_clips if c["fps"] and c["fps"] != project_fps]

print(f"Offline: {len(offline)}")
print(f"Duplicate file paths: {len(duplicates)}")
print(f"FPS mismatches (project={project_fps}): {len(mismatched_fps)}")
```

Report issues to the user before proceeding:

```
## Media Pool Health Check

- **Total clips**: N
- **Offline media**: N (files not found on disk)
- **Duplicate entries**: N (same file imported multiple times)
- **Frame rate mismatches**: N (clips don't match project FPS of XX)
```

List specific offline and mismatched clips so the user can address them.

## Step 3 — Group clips by chosen criteria

```python
from collections import defaultdict
import re

groups = defaultdict(list)

for clip in all_clips:
    if strategy == "camera":
        # Camera metadata isn't always available; fall back to filename patterns
        key = clip.get("camera") or "Unknown Camera"
    elif strategy == "date":
        key = clip["date"].split(" ")[0] if clip["date"] else "Unknown Date"
    elif strategy == "resolution":
        key = clip["resolution"] or "Unknown Resolution"
    elif strategy == "codec":
        key = clip["codec"] or "Unknown Codec"
    elif strategy == "file_type":
        ext = os.path.splitext(clip["file_path"])[1].lower() if clip["file_path"] else ""
        key = ext if ext else "No Extension"
    elif strategy == "pattern":
        match = re.search(user_pattern, clip["name"])
        key = match.group(1) if match else "Unmatched"

    groups[key].append(clip)
```

## Step 4 — Preview the plan

Before moving anything, show the user what will happen:

```
## Organization Plan

| Bin | Clips |
|-----|-------|
| 4K/ | 45 clips |
| HD/ | 23 clips |
| Unknown Resolution/ | 3 clips |

Total: 71 clips will be moved into 3 bins.
```

Ask for confirmation:

> Does this look right? Should I proceed with organizing?

## Step 5 — Create bins and move clips

Only after the user confirms:

```python
root = media_pool.GetRootFolder()

# Create a parent folder for the organized bins
media_pool.SetCurrentFolder(root)
org_folder = media_pool.AddSubFolder(root, "Organized")
if org_folder is None:
    # Folder may already exist — find it
    for sf in root.GetSubFolderList():
        if sf.GetName() == "Organized":
            org_folder = sf
            break

moved = 0
for group_name, clips in groups.items():
    # Create bin for this group
    bin_folder = media_pool.AddSubFolder(org_folder, group_name)
    if bin_folder is None:
        for sf in org_folder.GetSubFolderList():
            if sf.GetName() == group_name:
                bin_folder = sf
                break

    if bin_folder:
        clip_objs = [c["clip_obj"] for c in clips]
        result = media_pool.MoveClips(clip_objs, bin_folder)
        if result:
            moved += len(clip_objs)
            print(f"Moved {len(clip_objs)} clips to {group_name}")
        else:
            print(f"Failed to move clips to {group_name}")

print(f"Total moved: {moved}")
```

## Step 6 — Report results

```
## Organization Complete

Organized N clips into M bins under "Organized/":
- Organized/4K/ — 45 clips
- Organized/HD/ — 23 clips
- Organized/Unknown Resolution/ — 3 clips

### Issues Found
- 2 offline clips (files not on disk)
- 1 duplicate entry
- 5 clips with mismatched frame rates
```

## Implementation notes

- **Guard against None**: `GetClipList()`, `GetSubFolderList()` can return None.
- **MoveClips**: `media_pool.MoveClips(clips_list, target_folder)` moves clips between bins.
- **AddSubFolder**: Returns None if the folder already exists — find the existing folder in that case.
- **Persistent variables**: All clip data and folder references survive across `run_resolve_code` calls.
- **Large media pools**: Break scanning into per-folder calls if the pool has hundreds of clips.
- **No deletions**: This command never deletes clips or bins. It only creates bins and moves clips.
- **Clip properties**: Available metadata depends on the clip type. Video clips have resolution, codec, FPS. Audio clips may lack video properties. Use `GetClipProperty()` with specific property names.

## Examples

```
/organize
```
