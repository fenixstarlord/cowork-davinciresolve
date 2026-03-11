"""
Execute individual API calls in DaVinci Resolve's scripting environment.
Maintains a persistent namespace so results carry across calls within a session.
"""

import io
import sys
import signal
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass
class ExecutionResult:
    success: bool
    output: str = ""
    error: str = ""
    return_value: Any = None

    def summary(self) -> str:
        """Short human-readable summary of the result."""
        if not self.success:
            return f"Error: {self.error}"
        parts = []
        if self.output:
            parts.append(self.output.strip())
        if self.return_value is not None:
            val = repr(self.return_value)
            if len(val) > 500:
                val = val[:500] + "..."
            parts.append(val)
        return "\n".join(parts) if parts else "OK (no output)"


class ExecutionTimeout(Exception):
    pass


@contextmanager
def timeout(seconds: int):
    """Context manager that raises ExecutionTimeout after the given seconds."""
    def handler(signum, frame):
        raise ExecutionTimeout(f"Execution timed out after {seconds} seconds.")

    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class ResolveExecutor:
    """Execute API calls in Resolve with a persistent namespace across calls."""

    TIMEOUT_SECONDS = 30

    def __init__(self, resolve_instance):
        self.resolve = resolve_instance
        # Persistent namespace — results from earlier calls are available to later ones
        self.namespace: dict = {}
        self._init_namespace()

    def _init_namespace(self):
        """Populate the namespace with the resolve entry point and common objects."""
        self.namespace["resolve"] = self.resolve
        if self.resolve:
            try:
                pm = self.resolve.GetProjectManager()
                if pm:
                    self.namespace["project_manager"] = pm
                    project = pm.GetCurrentProject()
                    if project:
                        self.namespace["project"] = project
                        self.namespace["media_pool"] = project.GetMediaPool()
                        timeline = project.GetCurrentTimeline()
                        if timeline:
                            self.namespace["timeline"] = timeline
            except Exception:
                pass

    def refresh_namespace(self):
        """Re-populate common objects (call after state-changing operations)."""
        self._init_namespace()

    def execute(self, code: str) -> ExecutionResult:
        """
        Execute a code snippet in the persistent namespace.

        Variables assigned in one call are available in subsequent calls,
        enabling multi-step workflows.
        """
        captured_output = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured_output

            with timeout(self.TIMEOUT_SECONDS):
                return_value = None

                # Try eval first (single expression) to capture return value
                try:
                    return_value = eval(code.strip(), self.namespace)
                    self.namespace["_"] = return_value
                except SyntaxError:
                    # Not a single expression — use exec
                    exec(code, self.namespace)

                    # Try to eval just the last line for a return value
                    lines = code.strip().split("\n")
                    last_line = lines[-1].strip()
                    if last_line and not _is_statement(last_line):
                        try:
                            return_value = eval(last_line, self.namespace)
                            self.namespace["_"] = return_value
                        except Exception:
                            pass

            return ExecutionResult(
                success=True,
                output=captured_output.getvalue(),
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


def _is_statement(line: str) -> bool:
    """Check if a line is a Python statement (not an expression)."""
    line = line.strip()
    if not line or line.startswith("#"):
        return True
    keywords = (
        "import ", "from ", "if ", "for ", "while ", "def ", "class ",
        "try:", "except", "finally:", "with ", "return ", "raise ",
        "pass", "break", "continue", "del ", "assert ", "elif ", "else:",
    )
    if any(line.startswith(kw) for kw in keywords):
        return True
    if "=" in line and not line.startswith("=") and "==" not in line.split("=")[0]:
        return True
    return False
