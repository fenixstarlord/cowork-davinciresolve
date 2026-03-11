# DaVinci Resolve RAG Chatbot

## Project Overview

RAG-powered chatbot that answers questions and generates executable scripts for DaVinci Resolve, grounded in local Resolve API and Fusion scripting documentation.

- Python 3.10+ CLI application
- Anthropic Claude API for LLM (via `anthropic` SDK)
- ChromaDB vector store with `sentence-transformers` embeddings (nomic-embed-text)
- Hybrid retrieval: vector similarity + BM25 keyword search with Reciprocal Rank Fusion
- CLI built with `click` and `rich`

## Architecture

```
User Query → Hybrid Retrieval (Vector + BM25) → Prompt Construction → Claude API → Validation → Response/Execution
```

### Core Modules (`src/`)

| Module | Purpose |
|---|---|
| `ingest.py` | Parse docs, chunk by object/method, embed, index into ChromaDB |
| `retriever.py` | Hybrid search (vector + BM25) merged via RRF |
| `tools.py` | Parse API docs into structured tool definitions for LLM function calling |
| `validator.py` | Whitelist-based validation — blocks code with undocumented API calls |
| `session.py` | Track Resolve environment state (project, timeline, media pool, page) |
| `planner.py` | Multi-step task decomposition and sequential execution |
| `chat.py` | LLM orchestration: prompt construction, response routing |
| `executor.py` | Sandboxed script execution in Resolve's scripting console (30s timeout) |
| `main.py` | CLI entrypoint with interactive chat loop |

### Key Files

- `docs/` — Pre-cleaned Resolve API and Fusion scripting documentation (source of truth)
- `examples/examples.json` — Few-shot example pairs for prompt injection
- `vectorstore/` — Persisted ChromaDB embeddings (gitignored, rebuilt via `ingest`)
- `main.py` (root) — Bootstrap script that creates venv, installs deps, builds index

## Setup & Run

```bash
# One command does everything (venv, deps, index, chat):
python main.py

# Or individual steps:
python main.py ingest    # Rebuild vector index
python main.py refresh   # Refresh Resolve session
```

## Environment

- Virtual environment: `.venv/` (auto-created by `main.py`)
- Config: `.env` (copy from `.env.example`, set `ANTHROPIC_API_KEY`)
- Embedding model: `nomic-ai/nomic-embed-text-v1.5`

## Coding Standards

- Type hints on all public functions
- No hallucinated API calls — if docs don't cover it, say so
- Validate all generated code against the method whitelist before execution
- Keep chunks at 300-600 tokens, never split mid-method
- The `resolve` object is the entry point; assume it exists in execution context

## Testing

```bash
# Activate venv first
source .venv/bin/activate

# Test ingestion
python -m src.ingest

# Test retrieval
python -c "from src.retriever import HybridRetriever; r = HybridRetriever(); print(r.retrieve('get current timeline'))"
```

## Important Constraints

- **No internet lookups** for API info — only use local docs in `docs/`
- **No fine-tuning** — pure RAG
- **CLI only** in v1 (Streamlit UI is future work)
- **Resolve must be running** for execution/session features; chat works offline
- **Always require user confirmation** before executing generated code
