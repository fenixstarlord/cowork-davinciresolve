---
description: Roundtrip render for the active timeline. Renders individual clips with the Premiere XML preset, exports an FCP 7 XML (which carries transforms, crops, opacity, sizing), renames the sequence to avoid conflicts, and imports the XML as a new timeline linked to the rendered media.
disable-model-invocation: true
argument-hint: "<render_output_path>"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /roundtrip

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Roundtrip render for the **active timeline**. Renders individual clips, exports the timeline as FCP 7 XML, and imports that XML as a new timeline pointing at the rendered media. All clip attributes (transforms, crops, compositing, sizing, audio levels) travel through the XML — no manual property copying needed.

**Important:** This command only affects the currently active timeline.

## Usage

```
/roundtrip <render_output_path>
```

If `render_output_path` is not provided, ask the user.

## Step 0 — Ask for handles

Before doing anything, ask the user:

> How many frames of handles do you want on each clip? (common: 0, 12, 24, 48)

Store the answer. The Resolve scripting API has no render-setting key for handles, so if the user wants handles and confirms their preset does not already bake them in, note that handles will need to be configured manually in the Deliver page before running the command. Proceed with the render either way.

## Step 1 — Identify the active timeline

```python
source_tl = project.GetCurrentTimeline()
source_tl_name = source_tl.GetName()
```

Tell the user which timeline will be rendered.

## Step 2 — Load preset and render

```python
# Load preset
if not project.LoadRenderPreset("Premiere XML"):
    presets = project.GetRenderPresetList()
    # Show presets to user, ask which to use, then load it
    # Do not proceed until a preset is loaded

# Individual clips mode
project.SetCurrentRenderMode(0)

# Target directory
import os
render_output_path = os.path.expanduser(render_output_path)
os.makedirs(render_output_path, exist_ok=True)
project.SetRenderSettings({
    "TargetDir": render_output_path,
    "SelectAllFrames": True
})

# Queue and start
job_id = project.AddRenderJob()
project.StartRendering(job_id)
```

Poll completion with **separate** `run_resolve_code` calls (30-second timeout per call):

```python
status = project.GetRenderJobStatus(job_id)
in_progress = project.IsRenderingInProgress()
```

Report percentage to the user. Wait 3 seconds between polls.

## Step 3 — Export source timeline as FCP 7 XML

After the render finishes, make sure the source timeline is still active and export:

```python
project.SetCurrentTimeline(source_tl)
xml_path = os.path.join(render_output_path, f"{source_tl_name}.xml")
source_tl.Export(xml_path, resolve.EXPORT_FCP_7_XML, resolve.EXPORT_NONE)
```

The exported XML carries all clip attributes as `<filter>` / `<parameter>` elements:

| XML filter | What it carries |
|---|---|
| Basic Motion (`effectid: basic`) | Scale, Center (pan/tilt), Rotation, Anchor Point |
| Crop (`effectid: crop`) | left, right, top, bottom |
| Opacity (`effectid: opacity`) | opacity value |
| Composite Mode (`<compositemode>`) | blend mode |
| Audio Levels (`effectid: audiolevels`) | level |
| Audio Pan (`effectid: audiopan`) | pan |

The video `<pathurl>` elements will already point to the rendered clips in `render_output_path` because Resolve updates media pool references after rendering.

## Step 4 — Rename sequence in XML and import

The `<sequence><name>` inside the XML **must not match** any existing timeline name or the import will silently fail. Parse and rename it:

```python
import xml.etree.ElementTree as ET

tree = ET.parse(xml_path)
root = tree.getroot()

# Rename sequence
for seq in root.iter('sequence'):
    name_elem = seq.find('name')
    if name_elem is not None:
        name_elem.text = f"{source_tl_name} - Roundtrip"

# Save modified XML
modified_xml = os.path.join(render_output_path, f"{source_tl_name}_roundtrip.xml")
tree.write(modified_xml, xml_declaration=True, encoding='utf-8')

# Import
new_tl = media_pool.ImportTimelineFromFile(modified_xml, {})
```

If `new_tl` is None, report the error. Common causes:
- Sequence name collision — pick a different name and retry
- Missing rendered media — verify files exist in `render_output_path`

## Step 5 — Verify and report

Switch to the new timeline and spot-check a few clips:

```python
project.SetCurrentTimeline(new_tl)
items = new_tl.GetItemListInTrack("video", 1)
for item in items:
    if item.GetProperty() is None:
        continue  # transition
    zx = item.GetProperty("ZoomX")
    mp = item.GetMediaPoolItem()
    fpath = mp.GetClipProperty("File Path") if mp else "?"
    print(f"{item.GetName()} — ZoomX={zx} — {fpath}")
```

Report to the user:
- Source timeline name
- New timeline name
- Number of clips on the new timeline
- Render output path
- Confirmation that clips point to rendered media and transforms are intact

## Implementation notes

- **1-based indexing** for tracks: `GetItemListInTrack("video", 1)` is the first video track.
- **Skip transitions**: `item.GetProperty()` returns `None` for transitions.
- **Guard against None**: `GetItemListInTrack()` can return None.
- **Render polling**: Each poll must be a separate `run_resolve_code` call.
- **Persistent variables**: `source_tl` and `new_tl` survive across `run_resolve_code` calls within the same session.
- **Audio pathurls**: Audio `<pathurl>` elements point to original source files (not rendered). This is correct — audio doesn't need roundtripping.
- **XML pathurl format**: Uses `file://localhost/` prefix with forward slashes and `%20` for spaces. On Windows: `file://localhost/D:/path/to/file.mov`. On macOS: `file://localhost/Volumes/DriveName/path/to/file.mov` or `file://localhost/Users/name/path/to/file.mov`.
- **Cross-platform paths**: Always use `os.path.join()` and `os.makedirs()` for path construction. The `render_output_path` from the user may use either `/` or `\` separators — Python's `os.path` handles both.

## Examples

```
/roundtrip D:/Projects/ETO/Renders/Roundtrip/roundtrip
/roundtrip /Volumes/Media/Projects/MyProject/Renders/260317
/roundtrip ~/Desktop/Roundtrip
```
