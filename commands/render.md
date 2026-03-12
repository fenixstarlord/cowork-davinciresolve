---
description: Set up and start render jobs for the active timeline
argument-hint: "<format, codec, and output path>"
---

# /render

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Set up render settings and start render jobs for the **active timeline** unless the user specifies otherwise.

## Usage
/render $ARGUMENTS

## How It Works
1. Use ~~resolve to check the current project and active timeline — tell the user which timeline will be rendered
2. Configure render settings (format, codec, resolution, output path)
3. Add render job(s) to the queue
4. Optionally start rendering
5. Report the render job status

## Examples
- `/render ProRes 422 HQ to ~/Desktop/exports`
- `/render H.264 1080p for YouTube`
- `/render all timelines as DNxHR HQX to /Volumes/Export/`
- `/render current timeline as PNG sequence`

## Notes
- Render format and codec names must match what Resolve supports — use `project.GetRenderFormats()` and `project.GetRenderCodecs(format)` to list available options
- Resolution and frame rate come from project settings unless overridden
