---
name: fusion-scripting
description: Fusion scripting guide for DaVinci Resolve's Fusion page. Trigger when the user asks about Fusion compositions, nodes, scripting in Fusion, or visual effects automation.
---

# Fusion Scripting Guide

Use `~~resolve` to execute Fusion scripting code via `run_resolve_code`.

The full Fusion Scripting Guide is available as a resource at `resolve://fusion-docs`. Read it when you need to look up Fusion-specific APIs, node types, or scripting patterns.

## Quick Reference

### Accessing Fusion from a Timeline Item

```python
# Get Fusion comp from a timeline clip
timeline = project.GetCurrentTimeline()
items = timeline.GetItemListInTrack("video", 1)
item = items[0]
fusion_comp = item.GetFusionCompByIndex(1)
```

### Common Fusion Operations

- **Get comp**: `item.GetFusionCompByIndex(1)` — 1-based index
- **Get comp count**: `item.GetFusionCompCount()`
- **Add tool**: Via Fusion scripting within the comp
- **Comp name list**: `item.GetFusionCompNameList()`

### Key Concepts

- Fusion comps are per-timeline-item (per clip)
- Node-based compositing — tools are connected in a flow
- MediaIn/MediaOut are the input/output nodes connecting to the timeline
- Scripting languages: Lua (native) and Python
