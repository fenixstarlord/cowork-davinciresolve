"""
LLM orchestration, prompt construction, and response routing.
Central coordinator for the chatbot pipeline.
"""

import json
import os
import re
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
5. If a task requires multiple steps, present the COMPLETE script in a single Python code block rather than one tool call at a time.
6. Prefer generating complete Python scripts in code blocks over using individual tool calls. Tool calls are for simple single-method queries.

When providing code, wrap it in a Python code block. The code should be ready to execute in Resolve's scripting console."""


class ChatOrchestrator:
    """Central coordinator for the chatbot pipeline."""

    MAX_TOOL_ROUNDS = 10  # Safety limit for agentic tool-use loops

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
            query_words = set(query_lower.split())
            for tag in ex.get("tags", []):
                if tag.lower() in query_words or tag.lower() in query_lower:
                    score += 2
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

        Implements an agentic loop: if the LLM returns tool calls, the results
        are fed back so the LLM can continue its multi-step plan until it
        produces a final text response.

        Returns:
            Dict with 'response' (text), 'code' (if generated), 'validation', 'tool_calls'.
        """
        system, messages = self._build_messages(user_input)

        # Get tool definitions if available
        tools = None
        if self.tool_registry:
            tools = self.tool_registry.get_tool_definitions_for_llm()

        all_text_parts = []
        all_code_parts = []
        all_tool_calls = []

        for _round in range(self.MAX_TOOL_ROUNDS):
            kwargs = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "system": system,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            # Collect text and tool_use blocks from this response
            tool_use_blocks = []
            assistant_content = []

            for block in response.content:
                assistant_content.append(block)
                if block.type == "text":
                    all_text_parts.append(block.text)
                    code_blocks = re.findall(r"```python\s*\n(.*?)```", block.text, re.DOTALL)
                    all_code_parts.extend(code_blocks)
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)
                    all_tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            # If no tool calls, we're done — final text response
            if not tool_use_blocks:
                break

            # Append the assistant message with tool_use blocks
            messages.append({"role": "assistant", "content": assistant_content})

            # Build tool results and feed them back
            tool_results = []
            for block in tool_use_blocks:
                tool = self.tool_registry.get_tool_by_name(block.name) if self.tool_registry else None
                if tool:
                    # Build the code that would be executed
                    code = tool["resolve_call"]
                    for param_name, param_value in block.input.items():
                        code = code.replace(f"{{{param_name}}}", repr(param_value))
                    all_code_parts.append(code)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Tool call translated to code: `{code}`. This will be presented to the user for execution. Continue with your plan.",
                    })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Unknown tool: {block.name}. Please use a documented API method or provide a Python code block instead.",
                        "is_error": True,
                    })

            messages.append({"role": "user", "content": tool_results})

            # If stop_reason is end_turn (not tool_use), we're done
            if response.stop_reason != "tool_use":
                break

        # Assemble final result
        full_response = "\n".join(all_text_parts)
        full_code = "\n".join(all_code_parts) if all_code_parts else None

        # Validate generated code
        validation = None
        if full_code and self.validator:
            validation = self.validator.validate(full_code)

        # Update conversation history (store just the text summary)
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": full_response})

        return {
            "response": full_response,
            "code": full_code,
            "validation": validation,
            "tool_calls": all_tool_calls if all_tool_calls else None,
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
