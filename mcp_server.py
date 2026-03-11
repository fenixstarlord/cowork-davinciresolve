"""
DaVinci Resolve MCP Server — connects to Resolve and exposes tools for Claude Cowork.

Transport: stdio (launched by Claude Desktop via .mcp.json)
IMPORTANT: Never print to stdout — use stderr for logging.
"""

import ast
import io
import json
import os
import platform
import re
import signal
import sys
from contextlib import contextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ── Logging to stderr (stdout is reserved for MCP protocol) ──────────────────

def log(msg: str):
    print(msg, file=sys.stderr)


# ── Resolve Connection ───────────────────────────────────────────────────────

def _default_resolve_script_path() -> str:
    """Return the default Resolve scripting modules path for the current OS."""
    system = platform.system()
    if system == "Darwin":
        return "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
    elif system == "Windows":
        return os.path.join(
            os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
            r"Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
        )
    return "/opt/resolve/Developer/Scripting/Modules"


def _connect_resolve():
    """Try to connect to a running DaVinci Resolve instance."""
    resolve_script_path = os.environ.get(
        "RESOLVE_SCRIPT_PATH",
        _default_resolve_script_path(),
    )
    if resolve_script_path not in sys.path:
        sys.path.append(resolve_script_path)

    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        if resolve:
            log("Connected to DaVinci Resolve.")
        else:
            log("DaVinciResolveScript loaded but Resolve is not running.")
        return resolve
    except ImportError:
        log("Could not import DaVinciResolveScript. Check RESOLVE_SCRIPT_PATH.")
        return None
    except Exception as e:
        log(f"Error connecting to Resolve: {e}")
        return None


# ── Execution Engine (from src/executor.py) ──────────────────────────────────

class ExecutionTimeout(Exception):
    pass


@contextmanager
def timeout(seconds: int):
    """Context manager that raises ExecutionTimeout after the given seconds."""
    def handler(signum, frame):
        raise ExecutionTimeout(f"Execution timed out after {seconds} seconds.")

    # SIGALRM only available on Unix
    if hasattr(signal, "SIGALRM"):
        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        yield  # No timeout on Windows


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


# ── Validator (from src/validator.py) ────────────────────────────────────────

# Known Resolve object variable names — only direct calls on these are validated
RESOLVE_OBJECT_VARS = {
    "resolve", "project_manager", "pm", "project", "media_storage",
    "media_pool", "media_pool_item", "clip", "item", "folder",
    "root_folder", "timeline", "timeline_item", "gallery",
    "gallery_still", "gallery_still_album", "color_group", "fusion",
    "footage_folder", "timelines_folder", "current_folder",
    "broadcast_timeline", "web_timeline", "comp", "fusion_comp",
    "media_pool_folder",
}


def _extract_resolve_calls(code: str) -> list[tuple[str, str]]:
    """Extract direct method calls on known Resolve object variables."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fallback to regex
        pattern = r"\b(\w+)\.(\w+)\s*\("
        return [
            (obj, method)
            for obj, method in re.findall(pattern, code)
            if obj in RESOLVE_OBJECT_VARS
        ]

    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        value = node.func.value
        if isinstance(value, ast.Name) and value.id in RESOLVE_OBJECT_VARS:
            calls.append((value.id, node.func.attr))
    return calls


# ── Persistent Namespace ─────────────────────────────────────────────────────

_namespace: dict = {}
_resolve = None


def _init_namespace():
    """Populate the namespace with the resolve entry point and common objects."""
    global _resolve
    _namespace.clear()
    _resolve = _connect_resolve()
    _namespace["resolve"] = _resolve

    if _resolve:
        try:
            pm = _resolve.GetProjectManager()
            if pm:
                _namespace["project_manager"] = pm
                project = pm.GetCurrentProject()
                if project:
                    _namespace["project"] = project
                    _namespace["media_pool"] = project.GetMediaPool()
                    tl = project.GetCurrentTimeline()
                    if tl:
                        _namespace["timeline"] = tl
        except Exception as e:
            log(f"Warning: Could not fully populate namespace: {e}")


def _refresh_namespace():
    """Re-populate common objects (call after state-changing operations)."""
    _init_namespace()


# ── Load API method whitelist from docs ──────────────────────────────────────

def _load_valid_methods() -> set[str]:
    """Parse the API docs to extract valid method names."""
    docs_dir = Path(__file__).parent / "docs" / "resolve_api"
    methods = set()

    for doc_file in docs_dir.glob("*.txt"):
        try:
            text = doc_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Match lines like "  MethodName(args)" or "ClassName.MethodName(args)"
        for match in re.finditer(r"^\s+(\w+)\s*\(", text, re.MULTILINE):
            methods.add(match.group(1))

    log(f"Loaded {len(methods)} API methods from docs.")
    return methods


_valid_methods: set[str] = set()


# ── MCP Server Definition ───────────────────────────────────────────────────

mcp = FastMCP("DaVinci Resolve")

TIMEOUT_SECONDS = 30


@mcp.tool()
def run_resolve_code(code: str, description: str = "") -> str:
    """Execute Python code in DaVinci Resolve's scripting environment.

    The namespace is persistent: variables from previous calls are available.
    Pre-loaded variables: resolve, project_manager, project, media_pool, timeline.
    Use print() to output results. The last expression's value is also returned.

    Args:
        code: Python code to execute in the Resolve scripting environment.
        description: Optional brief description of what the code does.
    """
    if not _resolve:
        return "ERROR: Not connected to DaVinci Resolve. Call refresh_connection first, or ensure Resolve is running."

    # Validate against API whitelist
    if _valid_methods:
        calls = _extract_resolve_calls(code)
        invalid = [
            f"{obj}.{method}"
            for obj, method in calls
            if method not in _valid_methods
        ]
        if invalid:
            return f"WARNING: Unrecognized API calls: {', '.join(invalid)}. These may not be valid Resolve API methods. Proceeding anyway.\n"

    # Execute
    captured = io.StringIO()
    old_stdout = sys.stdout

    try:
        sys.stdout = captured

        with timeout(TIMEOUT_SECONDS):
            return_value = None

            try:
                return_value = eval(code.strip(), _namespace)
                _namespace["_"] = return_value
            except SyntaxError:
                exec(code, _namespace)
                lines = code.strip().split("\n")
                last_line = lines[-1].strip()
                if last_line and not _is_statement(last_line):
                    try:
                        return_value = eval(last_line, _namespace)
                        _namespace["_"] = return_value
                    except Exception:
                        pass

        output = captured.getvalue()
        parts = []
        if description:
            parts.append(f"[{description}]")
        parts.append("OK")
        if output.strip():
            parts.append(f"Output:\n{output.strip()}")
        if return_value is not None:
            val = repr(return_value)
            if len(val) > 1000:
                val = val[:1000] + "..."
            parts.append(f"Return value: {val}")
        return "\n".join(parts)

    except ExecutionTimeout as e:
        return f"TIMEOUT: {e}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    finally:
        sys.stdout = old_stdout


@mcp.tool()
def get_project_info() -> str:
    """Return current project name, timeline info, media pool structure, and current page.

    Quick read-only status check — no arguments needed.
    """
    if not _resolve:
        return "ERROR: Not connected to DaVinci Resolve. Ensure Resolve is running and call refresh_connection."

    info = {}
    try:
        info["current_page"] = _resolve.GetCurrentPage()
        pm = _resolve.GetProjectManager()
        project = pm.GetCurrentProject() if pm else None

        if project:
            info["project_name"] = project.GetName()
            info["timeline_count"] = project.GetTimelineCount()

            tl = project.GetCurrentTimeline()
            if tl:
                info["current_timeline"] = {
                    "name": tl.GetName(),
                    "video_tracks": tl.GetTrackCount("video"),
                    "audio_tracks": tl.GetTrackCount("audio"),
                }

            mp = project.GetMediaPool()
            if mp:
                root = mp.GetRootFolder()
                if root:
                    info["media_pool"] = _folder_summary(root)
        else:
            info["project_name"] = None
            info["note"] = "No project is currently open."

    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"

    return json.dumps(info, indent=2, default=str)


def _folder_summary(folder, depth=0, max_depth=3) -> dict:
    """Recursively summarize a media pool folder."""
    summary = {"name": folder.GetName()}
    clips = folder.GetClipList()
    summary["clip_count"] = len(clips) if clips else 0
    if clips and len(clips) <= 10:
        summary["clips"] = [c.GetName() for c in clips]

    if depth < max_depth:
        subfolders = folder.GetSubFolderList()
        if subfolders:
            summary["subfolders"] = [
                _folder_summary(sf, depth + 1, max_depth) for sf in subfolders
            ]
    return summary


@mcp.tool()
def refresh_connection() -> str:
    """Re-connect to DaVinci Resolve and refresh the namespace.

    Use after opening a new project, switching timelines, or if the connection drops.
    """
    _refresh_namespace()
    if _resolve:
        project_name = None
        try:
            pm = _resolve.GetProjectManager()
            proj = pm.GetCurrentProject() if pm else None
            project_name = proj.GetName() if proj else None
        except Exception:
            pass
        return f"Reconnected to Resolve. Current project: {project_name or '(none)'}"
    return "Could not connect to DaVinci Resolve. Ensure Resolve is running."


# ── Resources ────────────────────────────────────────────────────────────────

@mcp.resource("resolve://api-docs")
def get_api_docs() -> str:
    """DaVinci Resolve API documentation"""
    doc_path = Path(__file__).parent / "docs" / "resolve_api" / "resolve_api_v20.3.txt"
    try:
        return doc_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"API docs not found at {doc_path}"


@mcp.resource("resolve://fusion-docs")
def get_fusion_docs() -> str:
    """Fusion scripting guide documentation"""
    doc_path = Path(__file__).parent / "docs" / "fusion_scripting" / "fusion_scripting_guide.txt"
    try:
        return doc_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Fusion docs not found at {doc_path}"


@mcp.resource("resolve://examples")
def get_examples() -> str:
    """Few-shot examples for common DaVinci Resolve scripting tasks"""
    examples_path = Path(__file__).parent / "examples" / "examples.json"
    try:
        return examples_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Examples not found at {examples_path}"


# ── Startup ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("Starting DaVinci Resolve MCP server...")
    _valid_methods = _load_valid_methods()
    _init_namespace()
    mcp.run()
