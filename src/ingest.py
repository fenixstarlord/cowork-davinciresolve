"""
Document ingestion: parsing, chunking, embedding, and indexing into ChromaDB.
"""

import os
import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "./vectorstore")
DOCS_PATH = os.getenv("DOCS_PATH", "./docs")
COLLECTION_NAME = "resolve_docs"


def load_documents(docs_path: str) -> list[dict]:
    """Recursively load all .txt, .md, and .html files from the docs directory."""
    docs = []
    for root, _, files in os.walk(docs_path):
        for fname in sorted(files):
            if fname.endswith((".txt", ".md", ".html")):
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                rel_path = os.path.relpath(fpath, docs_path)
                docs.append({"source_file": rel_path, "content": content})
    return docs


def detect_object_name(header: str) -> str:
    """Extract the Resolve/Fusion object name from a section header."""
    header = header.strip()
    # Remove markdown heading markers
    header = re.sub(r"^#+\s*", "", header)
    # Take first word as object name
    match = re.match(r"^(\w+)", header)
    return match.group(1) if match else header


def chunk_document(doc: dict) -> list[dict]:
    """
    Chunk a document by object/class with method-level granularity.
    Keeps full context of each method together: signature, params, return type, description.
    """
    content = doc["content"]
    source_file = doc["source_file"]
    chunks = []

    # Split by object headers (lines that start with a word followed by methods indented below)
    # Pattern: a line starting at column 0 with an alphanumeric word (object name)
    # followed by indented method lines
    lines = content.split("\n")
    current_object = "General"
    current_section = "General"
    current_chunk_lines = []
    current_method = None
    chunk_index = 0

    def flush_chunk():
        nonlocal chunk_index
        text = "\n".join(current_chunk_lines).strip()
        if text and len(text) > 20:
            chunks.append({
                "text": text,
                "metadata": {
                    "source_file": source_file,
                    "object_name": current_object,
                    "method_name": current_method or "",
                    "section": current_section,
                    "chunk_index": chunk_index,
                },
            })
            chunk_index += 1

    for line in lines:
        stripped = line.strip()

        # Detect object headers: line at column 0, single word, alphanumeric
        if line and not line[0].isspace() and re.match(r"^[A-Z]\w+$", stripped):
            # Flush previous chunk
            if current_chunk_lines:
                flush_chunk()
                current_chunk_lines = []
            current_object = stripped
            current_section = stripped
            current_method = None
            current_chunk_lines.append(line)
            continue

        # Detect markdown headers
        md_header = re.match(r"^(#{1,4})\s+(.+)", line)
        if md_header:
            if current_chunk_lines:
                flush_chunk()
                current_chunk_lines = []
            header_text = md_header.group(2).strip()
            level = len(md_header.group(1))
            if level <= 2:
                current_object = detect_object_name(header_text)
                current_section = header_text
            else:
                current_section = header_text
            current_method = None
            current_chunk_lines.append(line)
            continue

        # Detect section headers with underlines (e.g., "Overview\n--------")
        if stripped and all(c == "-" for c in stripped) and len(stripped) >= 3:
            # The previous line was the header
            if current_chunk_lines:
                prev = current_chunk_lines[-1].strip()
                if prev and not all(c == "-" for c in prev):
                    flush_chunk()
                    current_chunk_lines = [current_chunk_lines[-1]] if current_chunk_lines else []
                    current_section = prev
                    obj = detect_object_name(prev)
                    if re.match(r"^[A-Z]", obj):
                        current_object = obj
                    current_method = None
            current_chunk_lines.append(line)
            continue

        # Detect method definitions (indented lines with function signatures)
        method_match = re.match(r"^\s{2,}(\w+)\(", line)
        if method_match:
            method_name = method_match.group(1)
            # If we have accumulated a substantial chunk, flush it
            if current_chunk_lines and current_method and current_method != method_name:
                # Check if chunk is getting large (approximate token count)
                text_so_far = "\n".join(current_chunk_lines)
                if len(text_so_far) > 400:
                    flush_chunk()
                    current_chunk_lines = [f"{current_object}"]
            current_method = method_name
            current_chunk_lines.append(line)
            continue

        # Regular content line
        current_chunk_lines.append(line)

        # Flush if chunk is getting too large (~600 tokens ≈ 2400 chars)
        text_so_far = "\n".join(current_chunk_lines)
        if len(text_so_far) > 2400:
            flush_chunk()
            current_chunk_lines = []
            current_method = None

    # Flush remaining
    if current_chunk_lines:
        flush_chunk()

    return chunks


def build_index(docs_path: str = None, vectorstore_path: str = None) -> list[dict]:
    """
    Parse docs, chunk them, generate embeddings, and persist to ChromaDB.
    Idempotent: re-running replaces the existing index.
    """
    docs_path = docs_path or DOCS_PATH
    vectorstore_path = vectorstore_path or VECTORSTORE_PATH

    print(f"Loading documents from {docs_path}...")
    documents = load_documents(docs_path)
    print(f"Found {len(documents)} document(s).")

    all_chunks = []
    for doc in documents:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)
    print(f"Generated {len(all_chunks)} chunks.")

    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)

    texts = [c["text"] for c in all_chunks]
    print("Generating embeddings...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    print(f"Persisting to ChromaDB at {vectorstore_path}...")
    os.makedirs(vectorstore_path, exist_ok=True)
    client = chromadb.PersistentClient(path=vectorstore_path)

    # Delete existing collection for idempotency
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Add in batches
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch_end = min(i + batch_size, len(all_chunks))
        batch_chunks = all_chunks[i:batch_end]
        batch_texts = [c["text"] for c in batch_chunks]
        batch_embeddings = embeddings[i:batch_end].tolist()
        batch_ids = [f"chunk_{j}" for j in range(i, batch_end)]
        batch_metadatas = [c["metadata"] for c in batch_chunks]

        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
        )

    print(f"Indexed {len(all_chunks)} chunks into collection '{COLLECTION_NAME}'.")
    return all_chunks


if __name__ == "__main__":
    build_index()
