"""
Multi-step task decomposition and sequential execution.

Breaks complex user requests into discrete steps, executes them in order,
and handles errors at each stage.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    description: str
    tool_calls: list[dict] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "tool_calls": self.tool_calls,
            "status": self.status.value,
            "result": str(self.result) if self.result else None,
            "error": self.error,
        }


@dataclass
class PlanResult:
    steps: list[Step]
    success: bool
    completed_count: int = 0
    failed_step: int | None = None
    error_message: str = ""

    def summary(self) -> str:
        parts = []
        for i, step in enumerate(self.steps, 1):
            icon = {
                StepStatus.COMPLETED: "[OK]",
                StepStatus.FAILED: "[FAIL]",
                StepStatus.SKIPPED: "[SKIP]",
                StepStatus.PENDING: "[--]",
                StepStatus.RUNNING: "[..]",
            }.get(step.status, "[??]")
            parts.append(f"  {icon} Step {i}: {step.description}")
            if step.error:
                parts.append(f"       Error: {step.error}")

        status = "SUCCESS" if self.success else "FAILED"
        header = f"Plan execution: {status} ({self.completed_count}/{len(self.steps)} steps completed)"
        return header + "\n" + "\n".join(parts)


class TaskPlanner:
    """Decomposes complex requests into steps and executes them sequentially."""

    PLANNING_PROMPT = """You are a DaVinci Resolve scripting planner. Given a user request,
break it down into a sequence of discrete steps. Each step should be a single
API operation or a small group of closely related operations.

Output a JSON array of steps. Each step has:
- "description": what this step does
- "code": the Python code to execute for this step
- "depends_on_previous": boolean, whether this step uses results from the previous step

Example output:
[
    {
        "description": "Get the current project",
        "code": "project = resolve.GetProjectManager().GetCurrentProject()",
        "depends_on_previous": false
    },
    {
        "description": "Get the media pool",
        "code": "media_pool = project.GetMediaPool()",
        "depends_on_previous": true
    }
]

Only use documented Resolve API methods. If you're unsure about an API call, note that in the description.
Return ONLY the JSON array, no other text."""

    def __init__(self):
        self.client = anthropic.Anthropic()

    def plan(self, user_request: str, context: dict) -> list[Step]:
        """
        Use the LLM to decompose a user request into a sequence of steps.

        Args:
            user_request: The user's natural language request.
            context: Dict with 'session_summary', 'retrieved_docs', etc.

        Returns:
            List of Step objects to execute.
        """
        import json

        messages = [
            {
                "role": "user",
                "content": (
                    f"Resolve environment:\n{context.get('session_summary', 'Not connected')}\n\n"
                    f"Relevant documentation:\n{context.get('retrieved_docs', 'No docs available')}\n\n"
                    f"User request: {user_request}\n\n"
                    "Break this request into execution steps."
                ),
            }
        ]

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=self.PLANNING_PROMPT,
            messages=messages,
        )

        response_text = response.content[0].text.strip()

        # Extract JSON from response
        try:
            # Try to find JSON array in the response
            json_match = response_text
            if "```" in response_text:
                # Extract from code block
                import re
                match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
                if match:
                    json_match = match.group(1)

            steps_data = json.loads(json_match)
        except json.JSONDecodeError:
            return [Step(
                description="Execute the full request",
                tool_calls=[{"code": response_text}],
            )]

        steps = []
        for step_data in steps_data:
            step = Step(
                description=step_data.get("description", ""),
                tool_calls=[{"code": step_data.get("code", "")}],
            )
            steps.append(step)

        return steps

    def execute_plan(self, steps: list[Step], session) -> PlanResult:
        """
        Execute a plan step by step.

        Args:
            steps: List of Step objects to execute.
            session: Session instance for accessing the Resolve environment.

        Returns:
            PlanResult with execution status.
        """
        from .executor import ResolveExecutor

        if not session.resolve:
            return PlanResult(
                steps=steps,
                success=False,
                error_message="Not connected to DaVinci Resolve.",
            )

        executor = ResolveExecutor(session.resolve)
        completed = 0

        for i, step in enumerate(steps):
            step.status = StepStatus.RUNNING
            code = step.tool_calls[0].get("code", "") if step.tool_calls else ""

            if not code:
                step.status = StepStatus.SKIPPED
                continue

            result = executor.execute(code)

            if result.success:
                step.status = StepStatus.COMPLETED
                step.result = result.return_value or result.output
                completed += 1
                # Update session after each step
                session.update_after_action(step.description, result)
            else:
                step.status = StepStatus.FAILED
                step.error = result.error or "Unknown error"
                # Mark remaining steps as skipped
                for remaining in steps[i + 1:]:
                    remaining.status = StepStatus.SKIPPED
                return PlanResult(
                    steps=steps,
                    success=False,
                    completed_count=completed,
                    failed_step=i,
                    error_message=f"Step {i + 1} failed: {step.error}",
                )

        return PlanResult(
            steps=steps,
            success=True,
            completed_count=completed,
        )
