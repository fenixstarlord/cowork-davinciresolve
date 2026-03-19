---
name: conform
description: Compare two timelines and report differences in clip order, durations, and edit points. Optionally auto-fix simple discrepancies.
user-invocable: true
argument-hint: "<reference_timeline_name>"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /conform

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Compare the **active timeline** against a reference timeline and generate a detailed conformance report. Identifies mismatches in clip order, durations, in/out points, and missing clips. Can optionally auto-fix simple discrepancies like slip edits.

**Important:** This command reads from both timelines but only modifies the active timeline (and only if the user opts in to auto-fix).

## Usage

```
/conform <reference_timeline_name>
```

If `reference_timeline_name` is not provided, list all timelines in the project and ask the user to pick the reference.

## Step 0 — Identify timelines

```python
active_tl = project.GetCurrentTimeline()
active_name = active_tl.GetName()

# Find the reference timeline by name
tl_count = project.GetTimelineCount()
ref_tl = None
for i in range(1, tl_count + 1):
    tl = project.GetTimelineByIndex(i)
    if tl.GetName() == reference_timeline_name:
        ref_tl = tl
        break
```

If `ref_tl` is None, report that the reference timeline was not found and list available timelines.

Tell the user: comparing **active_name** (active) against **reference_timeline_name** (reference).

## Step 1 — Extract clip data from both timelines

For each timeline, build a list of clip records from all video tracks:

```python
def extract_clips(tl):
    clips = []
    track_count = tl.GetTrackCount("video")
    for t in range(1, track_count + 1):
        items = tl.GetItemListInTrack("video", t)
        if items is None:
            continue
        for item in items:
            props = item.GetProperty()
            if props is None:
                continue  # transition
            mp = item.GetMediaPoolItem()
            clip_name = item.GetName()
            file_path = ""
            if mp:
                file_path = mp.GetClipProperty("File Path") or ""
            clips.append({
                "name": clip_name,
                "file_path": file_path,
                "track": t,
                "start": item.GetStart(),
                "end": item.GetEnd(),
                "duration": item.GetDuration(),
                "source_start": item.GetSourceStartFrame() if hasattr(item, 'GetSourceStartFrame') else None,
                "source_end": item.GetSourceEndFrame() if hasattr(item, 'GetSourceEndFrame') else None,
            })
    return clips

active_clips = extract_clips(active_tl)
ref_clips = extract_clips(ref_tl)
```

Store both lists in the persistent namespace for subsequent steps.

## Step 2 — Compare and generate report

Compare the two clip lists and categorize differences:

1. **Missing clips** — clips in the reference but not in the active timeline (match by file path + clip name)
2. **Extra clips** — clips in the active timeline but not in the reference
3. **Duration mismatches** — same clip present in both but with different durations
4. **Position mismatches** — same clip present in both but at different timeline positions (start frame)
5. **Source range mismatches** — same clip but different source in/out points (slip edits)
6. **Track mismatches** — same clip but on a different video track

```python
# Build lookup by (file_path, name) for matching
from collections import defaultdict

def build_lookup(clips):
    lookup = defaultdict(list)
    for i, c in enumerate(clips):
        key = (c["file_path"], c["name"])
        lookup[key].append((i, c))
    return lookup

active_lookup = build_lookup(active_clips)
ref_lookup = build_lookup(ref_clips)

missing = []
extra = []
duration_mismatches = []
position_mismatches = []
source_mismatches = []
track_mismatches = []

# Check reference clips against active
for key, ref_entries in ref_lookup.items():
    if key not in active_lookup:
        for _, c in ref_entries:
            missing.append(c)
    else:
        # Compare matched clips
        for ri, rc in ref_entries:
            matched = False
            for ai, ac in active_lookup[key]:
                if ac.get("_matched"):
                    continue
                ac["_matched"] = True
                matched = True
                if abs(rc["duration"] - ac["duration"]) > 0:
                    duration_mismatches.append({"ref": rc, "active": ac})
                if abs(rc["start"] - ac["start"]) > 0:
                    position_mismatches.append({"ref": rc, "active": ac})
                if rc["source_start"] is not None and ac["source_start"] is not None:
                    if rc["source_start"] != ac["source_start"] or rc["source_end"] != ac["source_end"]:
                        source_mismatches.append({"ref": rc, "active": ac})
                if rc["track"] != ac["track"]:
                    track_mismatches.append({"ref": rc, "active": ac})
                break
            if not matched:
                missing.append(rc)

# Extra clips in active not in reference
for key, active_entries in active_lookup.items():
    if key not in ref_lookup:
        for _, c in active_entries:
            extra.append(c)
```

## Step 3 — Present report

Present the conformance report to the user in a clear table format:

```
## Conformance Report: <active_name> vs <reference_name>

### Summary
- Matching clips: N
- Missing from active: N
- Extra in active: N
- Duration mismatches: N
- Position mismatches: N
- Source range mismatches: N
- Track mismatches: N

### Missing Clips (in reference but not in active)
| Clip | Track | Start | Duration |
...

### Duration Mismatches
| Clip | Ref Duration | Active Duration | Diff (frames) |
...

(etc. for each category)
```

Only show sections that have entries. If everything matches, report "Timelines are in conformance."

## Step 4 — Offer auto-fix (optional)

If there are source range mismatches (slip edits), ask the user:

> Would you like to auto-fix source range mismatches to match the reference timeline? This will adjust in/out points on N clips.

If the user agrees, apply the fixes on the **active timeline only**.

**Do not** auto-fix missing clips, extra clips, or track changes — those require editorial decisions.

## Implementation notes

- **1-based indexing** for tracks: `GetItemListInTrack("video", 1)` is the first video track.
- **Skip transitions**: `item.GetProperty()` returns `None` for transitions.
- **Guard against None**: `GetItemListInTrack()` can return None.
- **Persistent variables**: `active_tl`, `ref_tl`, and all clip lists survive across `run_resolve_code` calls.
- **Large timelines**: If a timeline has hundreds of clips, break the extraction into separate `run_resolve_code` calls per track to avoid the 30-second timeout.
- **Frame-accurate comparison**: All comparisons are frame-based (integer), no floating point issues.

## Examples

```
/conform Offline Edit v2
/conform Final Cut
/conform Assembly_v1
```
