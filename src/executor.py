"""
Execute validated scripts in DaVinci Resolve's scripting environment.
"""

import io
import sys
import signal
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    success: bool
    output: str = ""
    error: str = ""
    return_value: Any = None


class ExecutionTimeout(Exception):
    pass


@contextmanager
def timeout(seconds: int):
    """Context manager that raises ExecutionTimeout after the given seconds."""
    def handler(signum, frame):
        raise ExecutionTimeout(f"Script execution timed out after {seconds} seconds.")

    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class ResolveExecutor:
    """Execute validated scripts in Resolve's scripting environment."""

    TIMEOUT_SECONDS = 30

    def __init__(self, resolve_instance):
        self.resolve = resolve_instance

    def execute(self, code: str, namespace: dict = None) -> ExecutionResult:
        """
        Execute a validated Python script with access to the resolve object.

        Args:
            code: The Python code to execute.
            namespace: Optional shared namespace dict. If provided, code executes
                       in this namespace (allowing multi-step plans to share state).

        Returns:
            ExecutionResult with success status, output, errors, and return values.
        """
        if namespace is None:
            namespace = {}

        # Ensure resolve is available in the namespace
        namespace.setdefault("resolve", self.resolve)

        # Set up common convenience variables
        if self.resolve:
            try:
                pm = self.resolve.GetProjectManager()
                if pm:
                    namespace.setdefault("project_manager", pm)
                    project = pm.GetCurrentProject()
                    if project:
                        namespace.setdefault("project", project)
                        namespace.setdefault("media_pool", project.GetMediaPool())
                        timeline = project.GetCurrentTimeline()
                        if timeline:
                            namespace.setdefault("timeline", timeline)
            except Exception:
                pass

        # Capture stdout
        captured_output = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured_output

            with timeout(self.TIMEOUT_SECONDS):
                exec(code, namespace)

            output = captured_output.getvalue()

            # Try to extract a meaningful return value from the last expression
            return_value = None
            lines = code.strip().split("\n")
            if lines:
                last_line = lines[-1].strip()
                # If the last line is an expression (not assignment, not keyword statement)
                if (last_line and
                        "=" not in last_line and
                        not last_line.startswith(("import ", "from ", "if ", "for ",
                                                  "while ", "def ", "class ", "try:",
                                                  "except", "finally:", "with ", "#"))):
                    try:
                        return_value = eval(last_line, namespace)
                    except Exception:
                        pass

            return ExecutionResult(
                success=True,
                output=output,
                return_value=return_value,
            )

        except ExecutionTimeout as e:
            return ExecutionResult(
                success=False,
                output=captured_output.getvalue(),
                error=str(e),
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=captured_output.getvalue(),
                error=f"{type(e).__name__}: {e}",
            )
        finally:
            sys.stdout = old_stdout
