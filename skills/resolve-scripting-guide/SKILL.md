---
name: resolve-scripting-guide
description: Best practices and common patterns for DaVinci Resolve scripting. Trigger when generating code, planning automation tasks, or debugging Resolve scripts.
user-invocable: false
allowed-tools: Read, Grep, Glob, mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# Resolve Scripting Guide

## Connection

The MCP server maintains a persistent namespace with these pre-loaded variables:
- `resolve` — The Resolve application instance
- `project_manager` — `resolve.GetProjectManager()`
- `project` — Current project
- `media_pool` — `project.GetMediaPool()`
- `timeline` — Current timeline (if one is set)

If these become stale (e.g., after switching projects), call `refresh_connection`.

## Variable Naming Conventions

Always use these standard names for consistency:

```python
resolve          # Resolve app instance
project_manager  # or pm
project          # Current project
media_pool       # Media pool
media_storage    # Media storage (file system)
timeline         # Current timeline
folder           # Media pool folder
root_folder      # Root media pool folder
clip             # Media pool item / clip
item             # Timeline item
timeline_item    # Timeline item (alternative)
fusion_comp      # Fusion composition
```

## Common Gotchas

1. **1-based indexing** — `GetTimelineByIndex(1)` is the first timeline, not `0`
2. **Track indices are 1-based** — `GetItemListInTrack("video", 1)` for first video track
3. **mediaType values** — `1` = video only, `2` = audio only (for `AppendToTimeline`)
4. **SetLUT nodeIndex** — 1-based since DaVinci Resolve v16.2.0
5. **Render settings are strings** — `SetRenderSettings({"FormatWidth": "1920"})` not `1920`
6. **GetSubFolderList() can return None** — Always check before iterating
7. **GetClipList() can return None** — Always check before iterating
8. **Page names are lowercase** — `"edit"`, `"color"`, `"deliver"`, etc.

## Code Patterns

### Prefer loops over repeated calls

Instead of making separate `run_resolve_code` calls for each clip, write one call with a loop:

```python
# GOOD: One call with a loop
clips = folder.GetClipList()
if clips:
    for clip in clips:
        print(f"{clip.GetName()}: {clip.GetClipProperty('Duration')}")
```

### Always check for None

```python
timeline = project.GetCurrentTimeline()
if timeline is None:
    print("No timeline is currently selected")
else:
    print(f"Timeline: {timeline.GetName()}")
```

### Folder traversal

```python
def walk_folders(folder, depth=0):
    print("  " * depth + folder.GetName())
    clips = folder.GetClipList()
    if clips:
        for clip in clips:
            print("  " * (depth+1) + f"[clip] {clip.GetName()}")
    subfolders = folder.GetSubFolderList()
    if subfolders:
        for sf in subfolders:
            walk_folders(sf, depth+1)

root = media_pool.GetRootFolder()
walk_folders(root)
```

## Example Patterns

### Get all timelines
```python
count = project.GetTimelineCount()
timelines = [project.GetTimelineByIndex(i+1) for i in range(count)]
for t in timelines:
    print(t.GetName())
```

### Import media
```python
files = ["/path/to/clip1.mov", "/path/to/clip2.mp4"]
items = media_storage.AddItemListToMediaPool(files)
print(f"Imported {len(items)} items")
```

### Create timeline
```python
timeline = media_pool.CreateEmptyTimeline("My Timeline")
print(f"Created: {timeline.GetName()}")
```

### Render
```python
project.SetRenderSettings({
    "TargetDir": "/path/to/output",
    "CustomName": "MyRender"
})
job_id = project.AddRenderJob()
if job_id:
    project.StartRendering(job_id)
    print(f"Rendering started: {job_id}")
```

### Switch page
```python
resolve.OpenPage("color")
print(f"Now on: {resolve.GetCurrentPage()}")
```

### Get clips on track
```python
items = timeline.GetItemListInTrack("video", 1)
for item in items:
    print(f"{item.GetName()}: {item.GetStart()} - {item.GetEnd()}")
```

### Apply LUT
```python
items = timeline.GetItemListInTrack("video", 1)
items[0].SetLUT(1, "/path/to/my_lut.cube")
```

### Set resolution
```python
project.SetSetting("timelineResolutionWidth", "1920")
project.SetSetting("timelineResolutionHeight", "1080")
```

### Add track
```python
timeline.AddTrack("video")
print(f"Video tracks: {timeline.GetTrackCount('video')}")
```
