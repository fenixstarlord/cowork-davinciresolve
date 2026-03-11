---
name: resolve-script
description: Generate and validate DaVinci Resolve Python scripts using only documented API methods
allowed-tools: Read, Grep, Glob
---

When generating Resolve scripts:

1. **Search the docs** in `docs/` for the relevant API methods before writing any code
2. **Check `examples/examples.json`** for similar patterns to follow
3. **Validate** that every API call used exists in the documentation
4. **Use standard variable names**: `resolve`, `project_manager`, `project`, `media_pool`, `timeline`, `timeline_item`
5. **Assume `resolve` is available** as the entry point object

Always start scripts with the standard Resolve setup:
```python
project = resolve.GetProjectManager().GetCurrentProject()
```

Never guess API methods. If the docs don't cover it, say so explicitly.
Reference: `docs/resolve_api_v20.3.txt` and `docs/fusion_scripting_guide.txt`
