---
description: Create timelines from media pool clips with naming conventions
argument-hint: "<naming pattern and folder>"
---

# /create-timelines

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../CONNECTORS.md).

Create one or more timelines from clips in the media pool.

## Usage
/create-timelines $ARGUMENTS

## How It Works
1. Use ~~resolve to explore the media pool and find the source clips
2. Create timelines using the specified naming pattern
3. Move timelines to the specified folder (create it if needed)
4. Report what was created

## Examples
- `/create-timelines two per clip in FOOTAGE: <name>_BROADCAST and <name>_WEB, video only, put in TIMELINES folder`
- `/create-timelines one timeline per subfolder in FOOTAGE, named after the folder`
- `/create-timelines single timeline called "Master Edit" with all clips from root`
