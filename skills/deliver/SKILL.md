---
name: deliver
description: Set up and queue multi-format renders for the active timeline. Manages render presets, queues jobs, and monitors progress.
user-invocable: true
argument-hint: "<output_path>"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /deliver

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Set up and queue multi-format renders for the **active timeline**. Supports queuing multiple render presets in sequence, monitoring progress, and reporting completion.

**Important:** This command only affects the currently active timeline.

## Usage

```
/deliver <output_path>
```

If `output_path` is not provided, ask the user.

## Step 0 — Ask for delivery formats

Before doing anything, ask the user what formats they need. Present common options:

> What formats do you want to render? You can pick multiple:
>
> 1. **ProRes 422 HQ** (mastering)
> 2. **ProRes 422** (editing)
> 3. **DNxHR HQX** (mastering, Windows-friendly)
> 4. **H.265 Master** (high-quality archive)
> 5. **H.264 Review** (lightweight review copy)
> 6. **Use existing preset** (pick from your saved presets)
> 7. **Custom** (specify codec, resolution, bitrate)
>
> Or name a saved render preset from your Resolve installation.

Store the user's choices.

## Step 1 — Identify the active timeline

```python
tl = project.GetCurrentTimeline()
tl_name = tl.GetName()
```

Tell the user which timeline will be rendered and to which path.

## Step 2 — List available presets

```python
presets = project.GetRenderPresetList()
print(presets)
```

Show the user what presets are available if they chose "Use existing preset" or if a named preset doesn't match.

## Step 3 — Queue render jobs

For each requested format, configure and queue a render job. Create a subdirectory per format to keep outputs organized.

```python
import os

output_path = os.path.expanduser(output_path)

# Entire timeline mode
project.SetCurrentRenderMode(0)

jobs = []

for fmt in requested_formats:
    # Create subdirectory
    fmt_dir = os.path.join(output_path, fmt["subfolder"])
    os.makedirs(fmt_dir, exist_ok=True)

    # Try to load a preset if specified
    if fmt.get("preset"):
        if not project.LoadRenderPreset(fmt["preset"]):
            print(f"Preset '{fmt['preset']}' not found")
            continue

    # Apply render settings
    settings = {
        "TargetDir": fmt_dir,
        "SelectAllFrames": True,
    }

    # Add format-specific settings
    if fmt.get("format_name"):
        settings["FormatWidth"] = fmt.get("width", 0)
        settings["FormatHeight"] = fmt.get("height", 0)

    project.SetRenderSettings(settings)

    job_id = project.AddRenderJob()
    if job_id:
        jobs.append({"id": job_id, "name": fmt["name"], "dir": fmt_dir})
        print(f"Queued: {fmt['name']} -> {fmt_dir}")
    else:
        print(f"Failed to queue: {fmt['name']}")
```

**Important**: The exact render settings keys depend on the Resolve version. Common keys:

| Key | Description |
|-----|-------------|
| `TargetDir` | Output directory |
| `SelectAllFrames` | True = entire timeline |
| `MarkIn` / `MarkOut` | Custom range (frames) |
| `CustomName` | Output filename |

For codec-specific settings, loading a preset via `LoadRenderPreset()` is the most reliable approach. Encourage users to save presets in Resolve's Deliver page first.

## Step 4 — Start rendering and monitor

Start all queued jobs and poll for progress:

```python
project.StartRendering(isInteractiveMode=False)
```

Poll completion with **separate** `run_resolve_code` calls (30-second timeout per call):

```python
import json

in_progress = project.IsRenderingInProgress()
results = []
for job in jobs:
    status = project.GetRenderJobStatus(job["id"])
    results.append({
        "name": job["name"],
        "status": status.get("JobStatus", "Unknown"),
        "pct": status.get("CompletionPercentage", 0),
        "dir": job["dir"]
    })
    print(f"{job['name']}: {status.get('JobStatus', '?')} — {status.get('CompletionPercentage', 0)}%")
print(f"Rendering in progress: {in_progress}")
```

Report percentage to the user. Wait 5 seconds between polls. Continue polling until `IsRenderingInProgress()` returns False.

## Step 5 — Report results

After rendering completes, report for each job:

```python
for job in jobs:
    status = project.GetRenderJobStatus(job["id"])
    job_status = status.get("JobStatus", "Unknown")
    time_taken = status.get("TimeTakenToRenderInMs", 0)
    mins = time_taken // 60000
    secs = (time_taken % 60000) // 1000
    print(f"{job['name']}: {job_status} ({mins}m {secs}s) -> {job['dir']}")
```

Present a summary:

```
## Delivery Complete

| Format | Status | Time | Output |
|--------|--------|------|--------|
| ProRes 422 HQ | Complete | 2m 15s | /path/to/ProRes_HQ/ |
| H.264 Review | Complete | 0m 45s | /path/to/H264_Review/ |

All N jobs completed successfully.
```

If any jobs failed, report the error and suggest the user check render settings in the Deliver page.

## Implementation notes

- **1-based indexing** for tracks.
- **Render mode**: `SetCurrentRenderMode(0)` = Individual clips, no argument or timeline-specific mode for entire timeline. Check current behavior with `GetCurrentRenderMode()`.
- **Preset-first approach**: Loading a saved preset is more reliable than setting individual codec parameters via the API, since available settings vary by Resolve version.
- **Render polling**: Each poll must be a separate `run_resolve_code` call due to the 30-second timeout.
- **Persistent variables**: `jobs` list and `tl` survive across `run_resolve_code` calls.
- **Cross-platform paths**: Always use `os.path.join()` and `os.makedirs()`.
- **No StartRendering args for job IDs**: `StartRendering()` renders all queued jobs. To render specific jobs, pass job IDs: `StartRendering([job_id1, job_id2])`.

## Examples

```
/deliver ~/Desktop/Deliveries
/deliver D:/Projects/MyFilm/Deliveries
/deliver /Volumes/Media/Output/20260319
```
