---
name: resolve-api
description: DaVinci Resolve scripting API reference. Trigger when the user asks about Resolve API methods, objects, parameters, or scripting capabilities. Also trigger when generating code that calls Resolve API methods.
user-invocable: false
allowed-tools: Read, Grep, Glob, mcp__davinci-resolve__run_resolve_code, mcp__davinci-resolve__get_project_info, mcp__davinci-resolve__refresh_connection
---

# DaVinci Resolve Scripting API Reference

Use `~~resolve` to execute API calls. The primary tool is `run_resolve_code` which executes Python code in Resolve's scripting environment.

The full API documentation is available as a resource at `resolve://api-docs`. Read it when you need to look up specific method signatures, parameters, or return types.

## Key Objects

| Object | How to get it | Description |
|--------|--------------|-------------|
| `resolve` | Pre-loaded | Entry point to the Resolve scripting API |
| `project_manager` | `resolve.GetProjectManager()` | Manages projects |
| `project` | `project_manager.GetCurrentProject()` | Current project |
| `media_pool` | `project.GetMediaPool()` | Media pool access |
| `media_storage` | `resolve.GetMediaStorage()` | File system media access |
| `timeline` | `project.GetCurrentTimeline()` | Current timeline |
| `timeline_item` | `timeline.GetItemListInTrack(type, idx)` | Clips on timeline |
| `gallery` | `project.GetGallery()` | Gallery stills |

## Important Notes

- **1-based indexing**: Timeline tracks, render jobs, and node indices start at 1, not 0
- `GetTimelineByIndex(i)` uses 1-based index
- `SetLUT(nodeIndex, lutPath)` — nodeIndex is 1-based (since v16.2.0)
- `mediaType: 1` = video only, `mediaType: 2` = audio only
- Pages: `"media"`, `"cut"`, `"edit"`, `"fusion"`, `"color"`, `"fairlight"`, `"deliver"`
