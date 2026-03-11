# DaVinci Resolve Chatbot — Project Specification

## Overview

A RAG-powered chatbot that answers questions and generates executable scripts for DaVinci Resolve, grounded exclusively in local Resolve API and Fusion scripting documentation. The chatbot retrieves relevant documentation chunks, generates responses constrained to documented functionality, and optionally executes scripts directly in Resolve's scripting environment.

---

## Goals

- Answer user questions about DaVinci Resolve's scripting API accurately using only the local documentation.
- Generate valid, executable Python scripts for Resolve automation tasks.
- Refuse to hallucinate API calls — if the docs don't cover it, say so.
- Support multi-step task planning for complex workflows.
- Maintain session awareness of the user's current Resolve environment state.

---

## Project Structure

```
resolve-chatbot/
├── docs/                      # Pre-cleaned documentation (already prepared)
│   ├── resolve_api/
│   └── fusion_scripting/
├── src/
│   ├── ingest.py              # Doc parsing, chunking, embedding, and indexing
│   ├── retriever.py           # Hybrid retrieval (vector + BM25 keyword search)
│   ├── tools.py               # Tool definitions mapped to Resolve API methods
│   ├── validator.py           # Whitelist-based validation of generated API calls
│   ├── planner.py             # Multi-step task decomposition and sequential execution
│   ├── session.py             # Session context tracking (project, timeline, media pool state)
│   ├── chat.py                # LLM orchestration, prompt construction, few-shot examples
│   ├── executor.py            # Execute generated scripts in Resolve's scripting console
│   └── main.py                # CLI entrypoint
├── examples/                  # Few-shot example pairs (question → correct script)
│   └── examples.json
├── vectorstore/               # Persisted ChromaDB embeddings (gitignored)
├── requirements.txt
├── .env.example               # Template for API keys
├── .gitignore
└── spec.md                    # This file
```

---

## Tech Stack

| Component            | Choice                     | Rationale                                              |
| -------------------- | -------------------------- | ------------------------------------------------------ |
| Language             | Python 3.10+               | Resolve's scripting API is Python-native               |
| LLM                  | Anthropic Claude (via API) | Strong instruction following, long context window       |
| Embeddings           | `nomic-embed-text` via `sentence-transformers`, or OpenAI `text-embedding-3-small` | Good quality at low cost for this corpus size |
| Vector store         | ChromaDB                   | Simple, file-based, no infrastructure needed           |
| Keyword search       | `rank_bm25` (Python lib)   | Lightweight BM25 for hybrid retrieval                  |
| CLI interface        | `click` or `rich`          | Clean terminal UX for v1                               |
| Future UI            | Streamlit                  | Quick web UI when ready to move beyond CLI              |

---

## Component Specifications

### 1. Ingestion (`src/ingest.py`)

**Purpose:** Parse the pre-cleaned docs, chunk them, generate embeddings, and persist to ChromaDB.

**Chunking strategy:**
- Chunk by object/class with method-level granularity.
- Each chunk should keep the full context of a single method or concept together: function signature, parameters, return type, description, and any code examples.
- Never split mid-function or mid-parameter-table.
- Each chunk should include its parent context as metadata (e.g., which class/object it belongs to).
- Target chunk size: 300–600 tokens. Allow overflow for large method docs rather than splitting them.

**Metadata per chunk:**
- `source_file`: which doc file it came from
- `object_name`: the Resolve/Fusion object (e.g., `Timeline`, `MediaPool`, `Fusion`)
- `method_name`: specific method if applicable (e.g., `AddTrack`, `GetCurrentTimeline`)
- `section`: broader section/topic label
- `chunk_index`: ordering within the source

**Behavior:**
- Accept a path to the `docs/` directory.
- Recursively process all `.txt`, `.md`, or `.html` files in subdirectories.
- Output: populated ChromaDB collection persisted to `vectorstore/`.
- Should be idempotent — re-running replaces the existing index.

---

### 2. Hybrid Retriever (`src/retriever.py`)

**Purpose:** Given a user query, return the most relevant documentation chunks using a combination of vector similarity and keyword matching.

**Approach:**
- **Vector search:** Embed the query and retrieve top-K candidates from ChromaDB (K=10).
- **BM25 keyword search:** Run BM25 over all chunk texts using the raw query string. Retrieve top-K candidates (K=10).
- **Reciprocal Rank Fusion (RRF):** Merge results from both retrieval methods using RRF scoring to produce a single ranked list.
- Return the top 5–8 chunks after fusion.

**Why hybrid:** Pure vector search misses exact method names and parameter names. BM25 catches those. RRF combines them without needing tuned weights.

**Interface:**
```python
class HybridRetriever:
    def __init__(self, vectorstore_path: str, chunks: list[dict])
    def retrieve(self, query: str, top_k: int = 6) -> list[dict]
    # Returns list of chunk dicts with text, metadata, and RRF score
```

---

### 3. Tool Definitions (`src/tools.py`)

**Purpose:** Define each Resolve API method as a structured tool the LLM can invoke, rather than generating freeform code.

**Structure:**
- Parse the documentation during ingestion to extract a registry of all known API methods.
- Each tool definition includes:
  - `name`: fully qualified (e.g., `Timeline.AddTrack`)
  - `description`: what it does (from docs)
  - `parameters`: list of params with types and descriptions
  - `returns`: return type and description
  - `resolve_call`: the actual Python code template to invoke it

**Example tool definition:**
```python
{
    "name": "MediaPool.ImportMedia",
    "description": "Imports file paths into the current media pool folder.",
    "parameters": [
        {"name": "file_paths", "type": "list[str]", "description": "List of absolute file paths to import."}
    ],
    "returns": {"type": "list[MediaPoolItem]", "description": "List of imported media pool items."},
    "resolve_call": "media_pool.ImportMedia({file_paths})"
}
```

**Behavior:**
- The LLM selects tools and provides arguments.
- `chat.py` translates tool selections into executable code.
- This constrains the model to only produce valid, documented operations.

---

### 4. Validator (`src/validator.py`)

**Purpose:** Validate any generated code or tool calls against a whitelist of known API methods before execution.

**Behavior:**
- Maintain a set of all valid method names extracted from docs (built during ingestion).
- Before executing any generated script, parse it to extract all method calls.
- Reject any script that references methods not in the whitelist.
- Return clear error messages identifying which calls are invalid.

**Interface:**
```python
class APIValidator:
    def __init__(self, valid_methods: set[str])
    def validate(self, code: str) -> ValidationResult
    # ValidationResult includes: is_valid, invalid_calls, warnings
```

---

### 5. Multi-Step Planner (`src/planner.py`)

**Purpose:** Decompose complex user requests into a sequence of steps, execute them in order, and handle errors at each stage.

**Behavior:**
- When the user's request involves multiple operations (e.g., "import clips, create timeline, add clips, apply LUT"), the planner breaks it into discrete steps.
- Each step is a single tool call or a small group of related calls.
- Steps execute sequentially. After each step, capture the result (success/failure, return values).
- If a step fails, stop execution and report which step failed, why, and what completed successfully.
- Pass the results of prior steps as context to subsequent steps (e.g., a created timeline object is referenced in the next step).

**Interface:**
```python
class TaskPlanner:
    def plan(self, user_request: str, context: dict) -> list[Step]
    def execute_plan(self, steps: list[Step], session: Session) -> PlanResult
```

**The LLM generates the plan.** The planner module structures the prompt to ask the LLM to output a step-by-step plan in a structured format (JSON), then iterates through execution.

---

### 6. Session Context (`src/session.py`)

**Purpose:** Track the current state of the user's Resolve environment and inject it into every LLM prompt so responses are contextually aware.

**Tracked state:**
- Current project name and settings
- Active timeline name, track count, duration
- Media pool contents (folder structure, clip names)
- Current page (Edit, Color, Fusion, Deliver, etc.)
- Render settings if on the Deliver page

**Behavior:**
- On startup (or on explicit refresh command), query the Resolve API to populate the session state.
- Expose a `get_context_summary() -> str` method that produces a concise text summary suitable for injecting into prompts.
- Update state after each executed action (e.g., after creating a timeline, refresh timeline info).
- Keep it lightweight — don't deep-scan the entire project on every query, just maintain key navigational state.

**Interface:**
```python
class Session:
    def __init__(self, resolve_instance)
    def refresh(self)
    def get_context_summary(self) -> str
    def update_after_action(self, action: str, result: any)
```

---

### 7. Chat Orchestrator (`src/chat.py`)

**Purpose:** The central coordinator. Takes user input, retrieves context, constructs the prompt, calls the LLM, and routes the response.

**Prompt construction:**
1. **System prompt:** Sets the role, constraints, and output format. Key instruction: "You are a DaVinci Resolve scripting assistant. Only use the API methods described in the provided documentation. If the documentation does not cover a user's request, clearly state that rather than guessing."
2. **Session context:** Injected from `session.get_context_summary()`.
3. **Retrieved docs:** The top chunks from the hybrid retriever, formatted clearly with source labels.
4. **Few-shot examples:** 2–3 relevant examples pulled from `examples/examples.json`, selected based on similarity to the current query.
5. **Conversation history:** The last N turns of conversation for continuity.
6. **User message:** The current query.

**Available tool definitions** are passed to the LLM via the API's tool-use / function-calling feature so the model can invoke them directly.

**Flow:**
```
User input
  → retriever.retrieve(query)
  → select few-shot examples
  → construct prompt (system + session + docs + examples + history + query)
  → call LLM with tool definitions
  → if tool calls returned:
      → validator.validate(generated code)
      → if valid and user confirms: executor.execute(code)
      → update session state
  → return response to user
```

**Conversation history:** Maintain a rolling window of the last 10 turns. Summarize older turns if the context window gets tight.

---

### 8. Executor (`src/executor.py`)

**Purpose:** Execute validated scripts in DaVinci Resolve's scripting environment.

**Behavior:**
- Connect to Resolve's scripting API via the standard Python bridge (`DaVinciResolveScript`).
- Execute code in a sandboxed scope with access to the `resolve` object.
- Capture return values and print output.
- Catch and report exceptions cleanly.
- **Always require user confirmation before executing.** Display the code to the user first.

**Safety:**
- Only execute code that has passed the validator.
- Never execute arbitrary code the user pastes in — only code generated by the chatbot pipeline.
- Timeout after 30 seconds to prevent hanging on bad scripts.

**Interface:**
```python
class ResolveExecutor:
    def __init__(self, resolve_instance)
    def execute(self, code: str) -> ExecutionResult
    # ExecutionResult includes: success, output, error, return_value
```

---

### 9. CLI Entrypoint (`src/main.py`)

**Purpose:** Provide the user-facing interface.

**Commands:**
- **Default (no subcommand):** Start the interactive chat loop.
- `ingest`: Run the ingestion pipeline to (re)build the vector store.
- `refresh`: Manually refresh the session context from Resolve.

**Chat loop behavior:**
- Print a welcome message with the current Resolve project/timeline info (from session context).
- Accept natural language input.
- Display retrieved doc sources alongside answers (abbreviated, for transparency).
- When code is generated, display it and prompt: "Execute this in Resolve? [y/N]"
- Support `/quit`, `/refresh`, `/history` commands.

---

### 10. Few-Shot Examples (`examples/examples.json`)

**Purpose:** Provide high-quality question → script pairs to include in prompts as demonstrations.

**Format:**
```json
[
    {
        "question": "How do I get a list of all timelines in the current project?",
        "answer": "project = resolve.GetProjectManager().GetCurrentProject()\ncount = project.GetTimelineCount()\ntimelines = [project.GetTimelineByIndex(i+1) for i in range(count)]",
        "tags": ["project", "timeline", "list"]
    }
]
```

**Guidelines:**
- Start with 10–15 examples covering common operations: project management, timeline manipulation, media pool operations, rendering, Fusion composition basics.
- Tag each example so the chat module can select the most relevant ones per query.
- Expand over time as you use the chatbot and encounter new patterns.

---

## Environment & Configuration

**`.env.example`:**
```
ANTHROPIC_API_KEY=your-key-here
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
# Or for OpenAI embeddings:
# OPENAI_API_KEY=your-key-here
# EMBEDDING_MODEL=text-embedding-3-small
VECTORSTORE_PATH=./vectorstore
DOCS_PATH=./docs
RESOLVE_SCRIPT_PATH=/opt/resolve/Developer/Scripting/Modules  # Adjust per OS
```

**`requirements.txt`:**
```
anthropic
chromadb
sentence-transformers
rank_bm25
click
rich
python-dotenv
```

---

## Implementation Order

Build in this order — each step is independently testable:

1. **Ingestion** — Get docs chunked and indexed. Verify by inspecting chunks.
2. **Retriever** — Implement hybrid retrieval. Test with sample queries against the index.
3. **Validator** — Build the method whitelist and validation logic.
4. **Chat (basic)** — Wire up retrieval + LLM with a simple system prompt. No tools yet, just Q&A.
5. **Session** — Add Resolve connection and context tracking.
6. **Tools** — Define tool registry and integrate with LLM function calling.
7. **Planner** — Add multi-step decomposition for complex requests.
8. **Executor** — Add optional code execution with confirmation.
9. **CLI polish** — Commands, formatting, error handling.
10. **Few-shot examples** — Write examples and integrate selection logic.

---

## Constraints & Non-Goals

- **No internet lookups.** The chatbot must only use the local documentation in `docs/`. It should never search the web or reference knowledge outside the provided docs for API information.
- **No fine-tuning.** This is a RAG system, not a fine-tuned model.
- **No GUI in v1.** CLI only. Streamlit or web UI is a follow-up.
- **Single user.** No auth, no multi-tenancy. This runs locally alongside Resolve.
- **Resolve must be running.** The executor and session modules require a running Resolve instance. The chat and retrieval modules should work without Resolve running (in "offline" mode — answer questions but can't execute).
