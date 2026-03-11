"""
Tool definitions mapped to Resolve API methods.

Parses documentation to extract a registry of all known API methods,
structured as tool definitions the LLM can invoke.
"""

import re


def parse_api_methods(doc_text: str) -> list[dict]:
    """
    Parse the Resolve API documentation text to extract method definitions.

    Returns a list of tool definition dicts with:
        name, description, parameters, returns, resolve_call
    """
    tools = []
    current_object = None

    lines = doc_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect object headers (unindented single word starting with capital)
        if line and not line[0].isspace() and re.match(r"^[A-Z]\w+$", stripped):
            current_object = stripped
            i += 1
            continue

        # Detect method lines: indented, with function signature
        if current_object and line.startswith("  "):
            method_match = re.match(
                r"^\s+(\w+)\(([^)]*)\)\s*-->?\s*(.+?)(?:\s{2,}#\s*(.+))?$",
                line,
            )
            if method_match:
                method_name = method_match.group(1)
                params_str = method_match.group(2).strip()
                return_type = method_match.group(3).strip()
                description = method_match.group(4) or ""
                description = description.strip()

                # Collect continuation lines (additional description indented further)
                extra_desc_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if next_line.startswith("    ") and not re.match(r"^\s+\w+\(", next_line):
                        extra = next_line.strip()
                        if extra.startswith("#"):
                            extra = extra.lstrip("# ")
                        if extra:
                            extra_desc_lines.append(extra)
                        j += 1
                    else:
                        break

                if extra_desc_lines:
                    description = description + " " + " ".join(extra_desc_lines)
                    i = j - 1

                # Parse parameters
                parameters = _parse_params(params_str)

                # Build resolve_call template
                param_names = [p["name"] for p in parameters]
                args = ", ".join(f"{{{n}}}" for n in param_names)
                resolve_call = f"{_object_var(current_object)}.{method_name}({args})"

                tool = {
                    "name": f"{current_object}.{method_name}",
                    "description": description,
                    "parameters": parameters,
                    "returns": {
                        "type": return_type,
                        "description": "",
                    },
                    "resolve_call": resolve_call,
                }
                tools.append(tool)

        i += 1

    return tools


def _parse_params(params_str: str) -> list[dict]:
    """Parse a parameter string like 'name, value=True' into structured params."""
    if not params_str:
        return []

    params = []
    # Split on commas, but respect nested brackets/parens
    parts = _split_params(params_str)

    for part in parts:
        part = part.strip()
        if not part or part == "...":
            continue

        # Handle default values
        if "=" in part:
            name_part, default = part.split("=", 1)
            name_part = name_part.strip()
            default = default.strip()
        else:
            name_part = part
            default = None

        # Clean up name (remove type hints in brackets, etc.)
        name = re.sub(r"[\[\]{}\(\)]", "", name_part).strip()
        # Skip non-identifier params
        if not name or not re.match(r"^[a-zA-Z_]\w*$", name):
            continue

        param = {
            "name": name,
            "type": "any",
            "description": "",
        }
        if default is not None:
            param["default"] = default

        params.append(param)

    return params


def _split_params(s: str) -> list[str]:
    """Split parameter string by commas, respecting brackets."""
    parts = []
    depth = 0
    current = []
    for ch in s:
        if ch in "([{":
            depth += 1
            current.append(ch)
        elif ch in ")]}":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _object_var(object_name: str) -> str:
    """Convert an object name to a conventional variable name."""
    mapping = {
        "Resolve": "resolve",
        "ProjectManager": "project_manager",
        "Project": "project",
        "MediaStorage": "media_storage",
        "MediaPool": "media_pool",
        "MediaPoolItem": "media_pool_item",
        "MediaPoolFolder": "folder",
        "Timeline": "timeline",
        "TimelineItem": "timeline_item",
        "Gallery": "gallery",
        "GalleryStill": "gallery_still",
        "GalleryStillAlbum": "gallery_still_album",
        "Graph": "graph",
        "ColorGroup": "color_group",
    }
    return mapping.get(object_name, object_name.lower())


class ToolRegistry:
    """Registry of all Resolve API tools, built from documentation."""

    def __init__(self):
        self.tools: list[dict] = []
        self.method_names: set[str] = set()

    def load_from_docs(self, docs_path: str):
        """Load and parse all documentation files to build the tool registry."""
        import os

        for root, _, files in os.walk(docs_path):
            for fname in sorted(files):
                if fname.endswith((".txt", ".md")):
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    parsed = parse_api_methods(content)
                    self.tools.extend(parsed)

        self.method_names = {t["name"] for t in self.tools}

    def get_tool_definitions_for_llm(self) -> list[dict]:
        """
        Format tools as Anthropic-compatible tool definitions
        for the LLM's function-calling interface.
        """
        llm_tools = []
        for tool in self.tools:
            properties = {}
            required = []
            for param in tool["parameters"]:
                properties[param["name"]] = {
                    "type": "string",
                    "description": param.get("description", ""),
                }
                if "default" not in param:
                    required.append(param["name"])

            llm_tools.append({
                "name": tool["name"].replace(".", "_"),
                "description": f"{tool['name']}: {tool['description']}",
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return llm_tools

    def get_tool_by_name(self, name: str) -> dict | None:
        """Look up a tool by its fully qualified name (e.g. 'Timeline.AddTrack')."""
        # Accept both dotted and underscore forms
        normalized = name.replace("_", ".")
        for tool in self.tools:
            if tool["name"] == normalized or tool["name"] == name:
                return tool
        return None

    def get_valid_method_names(self) -> set[str]:
        """Return the set of all valid method names for validation."""
        return self.method_names
