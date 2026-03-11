---
description: Browse and inspect the media pool, timelines, and project structure
argument-hint: "<what to explore>"
---

# /explore

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Browse and inspect the media pool, timelines, clips, and project structure.

## Usage
/explore $ARGUMENTS

## How It Works
1. Use ~~resolve to query the specified part of the project
2. Display the results in a readable format
3. Offer follow-up actions if relevant

## Examples
- `/explore media pool` — Show all folders and clips
- `/explore timelines` — List all timelines with details
- `/explore current timeline` — Show tracks, clips, and markers on the current timeline
- `/explore clips in FOOTAGE folder` — List clips in a specific folder with properties
- `/explore render queue` — Show pending render jobs

## Notes
- Media pool folders are navigated recursively
- Clip properties include name, duration, resolution, frame rate, codec
- Timeline exploration shows track layout, clip placement, and markers
