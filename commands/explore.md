---
description: Browse and inspect the media pool, timelines, and project structure
argument-hint: "<what to explore>"
allowed-tools: mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# /explore

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Browse and inspect the media pool, timelines, clips, and project structure. When exploring timeline details, this operates on the **active timeline** unless the user specifies otherwise.

## Usage
/explore $ARGUMENTS

## How It Works
1. Use ~~resolve to query the specified part of the project
2. When exploring timeline details, use the active timeline unless another is specified
3. Display the results in a readable format
4. Offer follow-up actions if relevant

## Examples
- `/explore media pool` — Show all folders and clips
- `/explore timelines` — List all timelines with details
- `/explore current timeline` — Show tracks, clips, and markers on the active timeline
- `/explore clips in FOOTAGE folder` — List clips in a specific folder with properties
- `/explore render queue` — Show pending render jobs

## Notes
- Media pool folders are navigated recursively
- Clip properties include name, duration, resolution, frame rate, codec
- Timeline exploration shows track layout, clip placement, and markers
