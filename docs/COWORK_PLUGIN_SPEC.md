# Refactor: DaVinci Resolve Cowork Plugin

## Goal

Refactor the resolvechat project into a **Claude Cowork plugin** with a local MCP server. This replaces the custom CLI chatbot with a plugin that works natively in Claude Desktop's Cowork mode.

## What To Build

### Plugin Structure

```
resolvechat/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── .mcp.json                    # MCP connector config (points to local server)
├── mcp_server.py                # Python MCP server — connects to Resolve, exposes tools
├── CONNECTORS.md                # Documents the Resolve MCP connector
├── skills/
│   ├── resolve-api/
│   │   └── SKILL.md             # Resolve API reference (from docs/resolve_api/)
│   ├── fusion-scripting/
│   │   └── SKILL.md             # Fusion scripting reference (from docs/fusion_scripting/)
│   └── resolve-scripting-guide/
│       └── SKILL.md             # Best practices, common patterns, variable naming
├── commands/
│   ├── create-timelines.md      # /create-timelines slash command
│   ├── render.md                # /render slash command
│   ├── import-media.md          # /import-media slash command
│   ├── project-info.md          # /project-info slash command
│   └── explore.md               # /explore slash command (browse media pool/timelines)
├── docs/
│   ├── resolve_api/
│   │   └── resolve_api_v20.3.txt
│   ├── fusion_scripting/
│   │   └── fusion_scripting_guide.txt
│   └── spec.md
├── examples/
│   └── examples.json            # Few-shot examples (referenced by skills)
├── requirements.txt             # Just: mcp
├── setup.sh                     # Auto-installs deps and prints config instructions
├── CLAUDE.md
├── README.md                    # User-facing setup guide
└── .gitignore
```

### 1. Plugin Manifest (`.claude-plugin/plugin.json`)

```json
{
  "name": "davinci-resolve",
  "version": "1.0.0",
  "description": "Control DaVinci Resolve from Claude — execute API calls, create timelines, manage media, render projects. Requires Resolve to be running locally.",
  "author": {
    "name": "Your Name"
  }
}
```

### 2. MCP Connector Config (`.mcp.json`)

This tells Cowork to launch the local MCP server. Use `stdio` transport (the standard for local servers). The user will need to edit the path to match their installation.

```json
{
  "mcpServers": {
    "davinci-resolve": {
      "type": "stdio",
      "command": "python3",
      "args": ["mcp_server.py"],
      "env": {}
    }
  }
}
```

### 3. MCP Server (`mcp_server.py`)

Build using the `mcp` Python SDK (`from mcp.server.fastmcp import FastMCP`).

**Tools to expose:**

1. **`run_resolve_code`** — Execute a Python code snippet in Resolve's scripting environment. This is the primary tool. It should:
   - Maintain a persistent namespace across calls (`resolve`, `project_manager`, `project`, `media_pool`, `timeline` pre-loaded)
   - Capture stdout and return values
   - Have a 30-second timeout
   - Return success/failure, output text, and return value repr

2. **`get_project_info`** — Return current project name, timeline info, media pool structure, current page. Quick read-only status check.

3. **`refresh_connection`** — Re-connect to Resolve and refresh the namespace. Use after opening a new project or if the connection drops.

**Resources to expose:**

1. **`resolve://api-docs`** — The full Resolve API documentation text
2. **`resolve://fusion-docs`** — The full Fusion scripting guide text
3. **`resolve://examples`** — The few-shot examples JSON

**Implementation notes:**
- Use `from mcp.server.fastmcp import FastMCP` (the high-level API)
- Transport: stdio (default `mcp.run()`)
- Auto-detect the Resolve script path by platform (macOS/Windows/Linux) — reuse the `_default_resolve_script_path()` logic from `src/main.py`
- Connect to Resolve on startup via `DaVinciResolveScript.scriptapp("Resolve")`
- If Resolve isn't running, tools should return clear error messages (not crash)
- **Never print to stdout** in a stdio MCP server — use stderr for logging

**Example tool definition pattern:**
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("DaVinci Resolve")

@mcp.tool()
def run_resolve_code(code: str, description: str = "") -> str:
    """Execute Python code in DaVinci Resolve's scripting environment.

    The namespace is persistent: variables from previous calls are available.
    Pre-loaded variables: resolve, project_manager, project, media_pool, timeline.
    Use print() to output results.
    """
    # ... execute code, return results ...

@mcp.resource("resolve://api-docs")
def get_api_docs() -> str:
    """DaVinci Resolve API documentation"""
    # ... read and return docs/resolve_api/resolve_api_v20.3.txt ...

if __name__ == "__main__":
    mcp.run()
```

### 4. Skills

Skills are markdown files with YAML frontmatter. They provide domain knowledge that Claude draws on automatically when relevant.

**`skills/resolve-api/SKILL.md`:**
```yaml
---
name: resolve-api
description: DaVinci Resolve scripting API reference. Trigger when the user asks about Resolve API methods, objects, parameters, or scripting capabilities. Also trigger when generating code that calls Resolve API methods.
---
```
Then include the full API documentation content (from `docs/resolve_api/resolve_api_v20.3.txt`). This replaces the RAG pipeline — Claude reads the skill directly as context.

**`skills/fusion-scripting/SKILL.md`:**
Same pattern with the Fusion scripting guide content.

**`skills/resolve-scripting-guide/SKILL.md`:**
```yaml
---
name: resolve-scripting-guide
description: Best practices and common patterns for DaVinci Resolve scripting. Trigger when generating code, planning automation tasks, or debugging Resolve scripts.
---
```
Include:
- Standard variable naming conventions (`resolve`, `project`, `media_pool`, `timeline`, etc.)
- The few-shot examples from `examples/examples.json` formatted as example patterns
- Common gotchas (1-based indexing for timelines, `mediaType: 1` for video-only, etc.)
- How to connect to Resolve (`import DaVinciResolveScript as dvr_script`)

### 5. Commands

Commands are slash commands the user can invoke. Format:

**`commands/create-timelines.md`:**
```yaml
---
description: Create timelines from media pool clips with naming conventions
argument-hint: "<naming pattern and folder>"
---

# /create-timelines

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
```

**`commands/render.md`:**
```yaml
---
description: Set up and start render jobs for the current timeline or project
argument-hint: "<format, codec, and output path>"
---
```

**`commands/import-media.md`:**
```yaml
---
description: Import media files into the media pool
argument-hint: "<file paths or folder>"
---
```

**`commands/project-info.md`:**
```yaml
---
description: Show current project status — timelines, media pool, render queue
argument-hint: ""
---
```

**`commands/explore.md`:**
```yaml
---
description: Browse and inspect the media pool, timelines, and project structure
argument-hint: "<what to explore>"
---
```

### 6. CONNECTORS.md

```markdown
# Connectors

## How tool references work

This plugin uses `~~resolve` as a placeholder for the DaVinci Resolve MCP server.

## Connectors for this plugin

| Category | Placeholder | Server | Notes |
|----------|-------------|--------|-------|
| DaVinci Resolve | `~~resolve` | Local MCP server (`mcp_server.py`) | Requires Resolve running locally |

## Setup

1. Install the MCP server dependencies: `pip install mcp`
2. Ensure DaVinci Resolve is running
3. The plugin will auto-connect to Resolve via the local MCP server
```

### 7. Setup Script (`setup.sh`)

```bash
#!/bin/bash
pip install mcp
echo "Setup complete. Add this plugin to Claude Desktop:"
echo "  Settings > Plugins > Install from folder > select this directory"
```

### 8. README.md

Write a user-facing setup guide covering:
- Prerequisites (Python 3.10+, DaVinci Resolve running)
- Installation (clone repo, run setup.sh, add plugin to Claude Desktop)
- How to use in Cowork mode
- Available slash commands
- Troubleshooting (Resolve not detected, connection issues)

## What To Delete

These files are replaced by the plugin architecture and should be removed:
- `src/chat.py` — Cowork handles conversation
- `src/main.py` — Cowork is the UI
- `src/planner.py` — Claude handles planning natively
- `src/session.py` — Replaced by `get_project_info` tool
- `src/ingest.py` — Replaced by skills (docs as markdown)
- `src/retriever.py` — Replaced by skills (no RAG needed)
- `src/tools.py` — Replaced by MCP tool definitions
- `src/validator.py` — Keep the validation logic, move into mcp_server.py
- `src/__init__.py` — No longer needed
- `main.py` (bootstrap) — Replaced by setup.sh
- `vectorstore/` — No longer needed
- `.venv/` related logic — User manages their own Python env

## What To Keep/Reuse

- `src/executor.py` — The `ResolveExecutor` class with persistent namespace. Move the core logic into `mcp_server.py`
- `src/validator.py` — The `APIValidator` class. Integrate into `mcp_server.py` to validate code before execution
- `docs/` — The raw documentation files (referenced by skills)
- `examples/examples.json` — Reformatted into the scripting guide skill
- `.gitignore` — Update for new structure

## Dependencies

The only dependency is:
```
mcp
```

The `sentence-transformers`, `chromadb`, `rank_bm25`, `anthropic`, `click`, `rich` packages are no longer needed. Claude Desktop/Cowork provides the LLM, UI, and conversation management.

## Key Design Decisions

1. **Skills replace RAG** — The API docs are small enough to include as skills. Claude reads them directly when relevant. No embedding/chunking/vector store needed.

2. **`run_resolve_code` is the primary tool** — Rather than exposing hundreds of individual API methods as MCP tools, expose one flexible code execution tool. Claude writes the code using knowledge from the skills.

3. **Persistent namespace** — Variables from one `run_resolve_code` call carry to the next. This enables multi-step workflows without losing state.

4. **Commands are workflow templates** — They guide Claude through common tasks. The user can also just ask in natural language.

5. **Local stdio transport** — The MCP server runs locally alongside Resolve. No network/auth needed.
