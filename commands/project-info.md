---
description: Show current project status — timelines, media pool, render queue
argument-hint: ""
---

# /project-info

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Show a summary of the current DaVinci Resolve project.

## Usage
/project-info

## How It Works
1. Use ~~resolve `get_project_info` tool to get current project state
2. Display project name, current page, timeline info, and media pool structure
3. Show render queue status if any jobs exist

## Output Includes
- Project name
- Current page (Edit, Color, Deliver, etc.)
- Timeline count and current timeline details
- Media pool folder structure with clip counts
- Render queue status
