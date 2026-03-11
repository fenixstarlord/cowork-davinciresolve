"""
LLM orchestration, prompt construction, and response routing.
Central coordinator for the chatbot pipeline.
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from .retriever import HybridRetriever
from .validator import APIValidator
from .session import Session
from .tools import ToolRegistry
from .planner import TaskPlanner

load_dotenv()

EXAMPLES_PATH = os.getenv("EXAMPLES_PATH", "./examples/examples.json")

SYSTEM_PROMPT = """You are a DaVinci Resolve scripting assistant. You help users automate tasks in DaVinci Resolve using its Python scripting API.

CRITICAL RULES:
1. Only use the API methods described in the provided documentation. If the documentation does not cover a user's request, clearly state that rather than guessing.
2. Never hallucinate API calls. If you're unsure whether a method exists, say so.
3. When generating code, use the standard Resolve scripting setup: assume `resolve` is already available as the entry point object.
4. Always explain what the code does before presenting it.
5. If a task requires multiple steps, break it down clearly.

When providing code, wrap it in a Python code block. The code should be ready to execute in Resolve's scripting console."""


class ChatOrchestrator:
    """Central coordinator for the chatbot pipeline."""

    def __init__(
        self,
        retriever: HybridRetriever = None,
        session: Session = None,
        tool_registry: ToolRegistry = None,
        validator: APIValidator = None,
    ):
        self.client = anthropic.Anthropic()
        self.retriever = retriever
        self.session = session or Session()
        self.tool_registry = tool_registry
        self.validator = validator
        self.planner = TaskPlanner()
        self.conversation_history: list[dict] = []
        self.max_history = 10
        self.examples = self._load_examples()

    def _load_examples(self) -> list[dict]:
        """Load few-shot examples from examples.json."""
        examples_path = Path(EXAMPLES_PATH)
        if examples_path.exists():
            with open(examples_path, "r") as f:
                return json.load(f)
        return []

    def _select_examples(self, query: str, n: int = 3) -> list[dict]:
        """Select the most relevant few-shot examples for the query."""
        if not self.examples:
            return []

        query_lower = query.lower()
        scored = []
        for ex in self.examples:
            score = 0
            # Score based on tag overlap with query words
            query_words = set(query_lower.split())
            for tag in ex.get("tags", []):
                if tag.lower() in query_words or tag.lower() in query_lower:
                    score += 2
            # Score based on question similarity (simple word overlap)
            ex_words = set(ex.get("question", "").lower().split())
            overlap = len(query_words & ex_words)
            score += overlap
            scored.append((score, ex))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in scored[:n] if scored[0][0] > 0]

    def _format_retrieved_docs(self, chunks: list[dict]) -> str:
        """Format retrieved documentation chunks for the prompt."""
        if not chunks:
            return "No relevant documentation found."

        parts = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            source = meta.get("source_file", "unknown")
            obj = meta.get("object_name", "")
            method = meta.get("method_name", "")

            header = f"[Doc {i}] Source: {source}"
            if obj:
                header += f" | Object: {obj}"
            if method:
                header += f" | Method: {method}"

            parts.append(f"{header}\n{chunk['text']}")

        return "\n\n---\n\n".join(parts)

    def _format_examples(self, examples: list[dict]) -> str:
        """Format few-shot examples for the prompt."""
        if not examples:
            return ""

        parts = ["Here are some example question-answer pairs for reference:\n"]
        for ex in examples:
            parts.append(f"Q: {ex['question']}")
            parts.append(f"A:\n```python\n{ex['answer']}\n```\n")

        return "\n".join(parts)

    def _build_messages(self, user_input: str) -> tuple[str, list[dict]]:
        """
        Construct the full prompt with system, context, docs, examples, and history.

        Returns:
            Tuple of (system_prompt, messages_list).
        """
        # Retrieve relevant docs
        retrieved_docs = ""
        if self.retriever:
            chunks = self.retriever.retrieve(user_input, top_k=6)
            retrieved_docs = self._format_retrieved_docs(chunks)

        # Select few-shot examples
        examples = self._select_examples(user_input)
        examples_text = self._format_examples(examples)

        # Session context
        session_context = self.session.get_context_summary()

        # Build system prompt
        system = SYSTEM_PROMPT + "\n\n"
        system += f"## Current Resolve Environment\n{session_context}\n\n"
        system += f"## Relevant Documentation\n{retrieved_docs}\n"
        if examples_text:
            system += f"\n## Examples\n{examples_text}\n"

        # Build messages with history
        messages = []

        # Add conversation history (last N turns)
        history_window = self.conversation_history[-(self.max_history * 2):]
        messages.extend(history_window)

        # Add current user message
        messages.append({"role": "user", "content": user_input})

        return system, messages

    def chat(self, user_input: str) -> dict:
        """
        Process a user message through the full pipeline.

        Args:
            user_input: The user's natural language input.

        Returns:
            Dict with 'response' (text), 'code' (if generated), 'sources' (doc refs).
        """
        system, messages = self._build_messages(user_input)

        # Get tool definitions if available
        tools = None
        if self.tool_registry:
            tools = self.tool_registry.get_tool_definitions_for_llm()

        # Call the LLM
        kwargs = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)

        # Process response
        result = self._process_response(response)

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": result["response"]})

        return result

    def _process_response(self, response) -> dict:
        """Process the LLM response, extracting text and any tool calls."""
        text_parts = []
        code_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                # Extract code blocks from text
                import re
                code_blocks = re.findall(r"```python\s*\n(.*?)```", block.text, re.DOTALL)
                code_parts.extend(code_blocks)
            elif block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "input": block.input,
                })

        # If there were tool calls, generate code from them
        if tool_calls and self.tool_registry:
            for tc in tool_calls:
                tool = self.tool_registry.get_tool_by_name(tc["name"])
                if tool:
                    # Build executable code from tool call
                    code = tool["resolve_call"]
                    for param_name, param_value in tc["input"].items():
                        code = code.replace(f"{{{param_name}}}", repr(param_value))
                    code_parts.append(code)

        full_response = "\n".join(text_parts)
        full_code = "\n".join(code_parts) if code_parts else None

        # Validate generated code if we have a validator
        validation = None
        if full_code and self.validator:
            validation = self.validator.validate(full_code)

        return {
            "response": full_response,
            "code": full_code,
            "validation": validation,
            "tool_calls": tool_calls if tool_calls else None,
        }

    def get_sources(self, query: str) -> list[dict]:
        """Return the retrieved doc sources for transparency."""
        if not self.retriever:
            return []
        chunks = self.retriever.retrieve(query, top_k=6)
        return [
            {
                "source": c["metadata"].get("source_file", ""),
                "object": c["metadata"].get("object_name", ""),
                "method": c["metadata"].get("method_name", ""),
                "score": c.get("rrf_score", 0),
            }
            for c in chunks
        ]
