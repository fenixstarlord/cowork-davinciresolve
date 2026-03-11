---
name: rag-review
description: Review and diagnose the RAG pipeline — ingestion, embeddings, retrieval quality, and prompt construction
allowed-tools: Read, Grep, Glob, Bash
---

Analyze the RAG pipeline for issues:

1. **Ingestion** (`src/ingest.py`): Check chunking strategy, metadata extraction, and ChromaDB indexing
2. **Retrieval** (`src/retriever.py`): Verify hybrid search (vector + BM25), RRF fusion, and result ranking
3. **Embeddings**: Confirm the embedding model loads correctly and dimensions are consistent
4. **Prompt Construction** (`src/chat.py`): Review system prompt, context injection, and few-shot example selection
5. **Validation** (`src/validator.py`): Check that the method whitelist is complete and validation catches bad calls

Test retrieval quality by running sample queries against the index and reporting:
- Top chunks returned and their relevance
- Whether exact method names are matched (BM25 contribution)
- Whether semantic meaning is captured (vector contribution)

Report issues as: critical, warning, or suggestion.
