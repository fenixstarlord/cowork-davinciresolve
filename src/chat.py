"""
LLM orchestration with real-time tool execution.

The assistant makes individual API calls one at a time. Each call is
executed in Resolve, and the real result is fed back so the LLM can
decide what to do next. The CLI layer handles user confirmation (y/n/a)
between each step.
"""

import json
import os
import re
from pathlib import Path
from typing import Callable

import anthropic
from dotenv import load_dotenv

from .retriever import HybridRetriever
from .validator import APIValidator
from .session import Session
from .tools import ToolRegistry
from .executor import ResolveExecutor, ExecutionResult

load_dotenv()

EXAMPLES_PATH = os.getenv("EXAMPLES_PATH", "./examples/examples.json")

SYSTEM_PROMPT = """You are a DaVinci Resolve scripting assistant that executes API calls interactively.

HOW YOU WORK:
- You have a `run_code` tool for executing Python code in Resolve's scripting environment.
- The code runs in a persistent namespace where `resolve`, `project_manager`, `project`, `media_pool`, and `timeline` are pre-loaded.
- Variables you create in one call are available in the next.
- After each call, you receive the real output from DaVinci Resolve.

WORKFLOW FOR TASKS:
1. Start with a brief plan (2-3 sentences, not a full essay).
2. Use `run_code` to explore the current state (e.g., list folders, get clips).
3. Use `run_code` with the full logic (loops, conditionals, etc.) to accomplish the task.
4. Summarize what was done.

PREFER FEWER, LARGER STEPS: For batch operations (e.g., "create timelines for each clip"), write one `run_code` call with a loop — do NOT make a separate tool call for each clip. Keep it to 2-4 run_code calls total: explore, then execute, then verify.

RULES:
1. Only use documented API methods from the provided docs. Never guess.
2. If the docs don't cover something, say so.
3. Use print() in your code to show progress and results.
4. If a call fails, explain the error and suggest alternatives.

You also have individual Resolve API tools available, but prefer `run_code` for anything beyond a single method call."""


# Special tool for running arbitrary code blocks
RUN_CODE_TOOL = {
    "name": "run_code",
    "description": (
        "Execute a Python code snippet in Resolve's scripting environment. "
        "Use this for multi-line logic with loops, conditionals, or variable manipulation. "
        "The namespace is persistent: variables from previous calls are available. "
        "Pre-loaded variables: resolve, project_manager, project, media_pool, timeline."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Can be multi-line.",
            },
            "description": {
                "type": "string",
                "description": "Brief description of what this code does.",
            },
        },
        "required": ["code"],
    },
}


class StepInfo:
    """Information about a single execution step, passed to the UI callback."""

    def __init__(self, tool_name: str, description: str, code: str):
        self.tool_name = tool_name
        self.description = description
        self.code = code
        self.result: ExecutionResult | None = None
        self.skipped: bool = False


class ChatOrchestrator:
    """Agentic assistant that executes Resolve API calls one at a time."""

    MAX_TOOL_ROUNDS = 25  # Safety limit

    def __init__(
        self,
        retriever: HybridRetriever = None,
        session: Session = None,
        tool_registry: ToolRegistry = None,
        validator: APIValidator = None,
        executor: ResolveExecutor = None,
        on_step: Callable[[StepInfo], bool] = None,
    ):
        """
        Args:
            on_step: Callback invoked before each tool execution. Receives a
                StepInfo and should return True to execute, False to skip.
                If None, all steps execute automatically.
        """
        self.client = anthropic.Anthropic()
        self.retriever = retriever
        self.session = session or Session()
        self.tool_registry = tool_registry
        self.validator = validator
        self.executor = executor
        self.on_step = on_step
        self.conversation_history: list[dict] = []
        self.max_history = 10
        self.examples = self._load_examples()

    def _load_examples(self) -> list[dict]:
        examples_path = Path(EXAMPLES_PATH)
        if examples_path.exists():
            with open(examples_path, "r") as f:
                return json.load(f)
        return []

    def _select_examples(self, query: str, n: int = 3) -> list[dict]:
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
            score += len(query_words & ex_words)
            scored.append((score, ex))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in scored[:n] if scored[0][0] > 0]

    def _format_retrieved_docs(self, chunks: list[dict]) -> str:
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
        if not examples:
            return ""
        parts = ["Example question-answer pairs:\n"]
        for ex in examples:
            parts.append(f"Q: {ex['question']}")
            parts.append(f"A:\n```python\n{ex['answer']}\n```\n")
        return "\n".join(parts)

    def _build_system_prompt(self, user_input: str) -> str:
        retrieved_docs = ""
        if self.retriever:
            chunks = self.retriever.retrieve(user_input, top_k=6)
            retrieved_docs = self._format_retrieved_docs(chunks)

        examples = self._select_examples(user_input)
        examples_text = self._format_examples(examples)
        session_context = self.session.get_context_summary()

        system = SYSTEM_PROMPT + "\n\n"
        system += f"## Current Resolve Environment\n{session_context}\n\n"
        system += f"## Relevant Documentation\n{retrieved_docs}\n"
        if examples_text:
            system += f"\n## Examples\n{examples_text}\n"
        return system

    def _get_tools(self) -> list[dict]:
        """Get all tool definitions: Resolve API tools + run_code."""
        tools = []
        if self.tool_registry:
            tools = self.tool_registry.get_tool_definitions_for_llm()
        tools.append(RUN_CODE_TOOL)
        return tools

    def _build_code_for_tool(self, tool_name: str, tool_input: dict) -> str | None:
        """Translate a tool call into executable Python code."""
        if tool_name == "run_code":
            return tool_input.get("code", "")

        tool = self.tool_registry.get_tool_by_name(tool_name) if self.tool_registry else None
        if not tool:
            return None

        code = tool["resolve_call"]
        for param_name, param_value in tool_input.items():
            code = code.replace(f"{{{param_name}}}", repr(param_value))
        return code

    def chat(self, user_input: str, on_text: Callable[[str], None] = None) -> dict:
        """
        Process a user message with real-time tool execution.

        The LLM makes tool calls one at a time. Each is executed in Resolve
        via the executor, and real results are fed back.

        Args:
            user_input: The user's message.
            on_text: Optional callback for streaming text responses to the UI
                     as they arrive (before the agentic loop finishes).

        Returns:
            Dict with 'response' (final text), 'steps' (list of StepInfo).
        """
        system = self._build_system_prompt(user_input)
        tools = self._get_tools()

        # Build messages with history
        messages = []
        history_window = self.conversation_history[-(self.max_history * 2):]
        messages.extend(history_window)
        messages.append({"role": "user", "content": user_input})

        all_text_parts = []
        steps: list[StepInfo] = []

        for _round in range(self.MAX_TOOL_ROUNDS):
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system,
                messages=messages,
                tools=tools,
            )

            # Process response blocks
            tool_use_blocks = []
            assistant_content = []

            for block in response.content:
                assistant_content.append(block)
                if block.type == "text" and block.text.strip():
                    all_text_parts.append(block.text)
                    if on_text:
                        on_text(block.text)
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            # No tool calls — done
            if not tool_use_blocks:
                break

            # Append assistant message
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool call and feed results back
            tool_results = []
            for block in tool_use_blocks:
                code = self._build_code_for_tool(block.name, block.input)
                description = block.input.get("description", "") if block.name == "run_code" else block.name

                if code is None:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Unknown tool: {block.name}",
                        "is_error": True,
                    })
                    continue

                # Create step info
                step = StepInfo(
                    tool_name=block.name,
                    description=description,
                    code=code,
                )

                # Ask user for approval via callback
                should_execute = True
                if self.on_step:
                    should_execute = self.on_step(step)

                if should_execute and self.executor:
                    # Validate first
                    if self.validator:
                        validation = self.validator.validate(code)
                        if not validation.is_valid:
                            step.result = ExecutionResult(
                                success=False,
                                error=f"Validation failed: {validation}",
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Blocked: {validation}. Use only documented API methods.",
                                "is_error": True,
                            })
                            steps.append(step)
                            continue

                    # Execute
                    result = self.executor.execute(code)
                    step.result = result
                    self.session.update_after_action(description, result)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.summary(),
                        "is_error": not result.success,
                    })
                elif not self.executor:
                    step.skipped = True
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Resolve is not connected. Cannot execute.",
                        "is_error": True,
                    })
                else:
                    step.skipped = True
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "User skipped this step.",
                    })

                steps.append(step)

            messages.append({"role": "user", "content": tool_results})

            if response.stop_reason != "tool_use":
                break

        full_response = "\n".join(all_text_parts)

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": full_response})

        return {
            "response": full_response,
            "steps": steps,
        }

    def get_sources(self, query: str) -> list[dict]:
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
