"""
Whitelist-based validation of generated API calls.
Ensures generated code only references documented Resolve API methods.
"""

import ast
import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid: bool
    invalid_calls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.is_valid:
            return "Validation passed."
        parts = ["Validation FAILED."]
        if self.invalid_calls:
            parts.append(f"Invalid API calls: {', '.join(self.invalid_calls)}")
        if self.warnings:
            parts.append(f"Warnings: {'; '.join(self.warnings)}")
        return " ".join(parts)


class APIValidator:
    """Validates generated code against a whitelist of known Resolve API methods."""

    # Known Resolve objects that methods are called on
    KNOWN_OBJECTS = {
        "resolve", "project_manager", "project", "media_storage", "media_pool",
        "media_pool_item", "folder", "timeline", "timeline_item", "gallery",
        "gallery_still", "gallery_still_album", "color_group", "fusion",
    }

    # Built-in Python functions/methods that are always allowed
    ALLOWED_BUILTINS = {
        "print", "len", "range", "str", "int", "float", "list", "dict",
        "tuple", "set", "bool", "type", "isinstance", "enumerate", "zip",
        "sorted", "reversed", "min", "max", "sum", "abs", "round",
        "append", "extend", "insert", "remove", "pop", "keys", "values",
        "items", "get", "update", "format", "join", "split", "strip",
        "replace", "lower", "upper", "startswith", "endswith",
    }

    def __init__(self, valid_methods: set[str]):
        """
        Args:
            valid_methods: Set of fully qualified method names (e.g., 'Timeline.AddTrack').
        """
        self.valid_methods = valid_methods
        # Build a set of just method names (without object prefix) for matching
        self._method_names_only = {m.split(".")[-1] for m in valid_methods}

    def validate(self, code: str) -> ValidationResult:
        """
        Validate generated code against the API whitelist.

        Parses the code to extract method calls and checks each one against
        the whitelist. Returns a ValidationResult.
        """
        invalid_calls = []
        warnings = []

        # Try AST-based extraction first
        try:
            calls = self._extract_calls_ast(code)
        except SyntaxError:
            calls = self._extract_calls_regex(code)
            warnings.append("Code has syntax errors; used regex-based validation (less accurate).")

        for call in calls:
            method_name = call.split(".")[-1] if "." in call else call

            # Skip known builtins
            if method_name in self.ALLOWED_BUILTINS:
                continue

            # Skip Python dunder methods
            if method_name.startswith("__") and method_name.endswith("__"):
                continue

            # Check against whitelist
            if method_name not in self._method_names_only:
                # Check with object prefix
                if call not in self.valid_methods:
                    invalid_calls.append(call)

        return ValidationResult(
            is_valid=len(invalid_calls) == 0,
            invalid_calls=invalid_calls,
            warnings=warnings,
        )

    def _extract_calls_ast(self, code: str) -> list[str]:
        """Extract method calls using Python AST parsing."""
        tree = ast.parse(code)
        calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name:
                    calls.append(call_name)

        return calls

    @staticmethod
    def _get_call_name(node: ast.Call) -> str | None:
        """Extract the full dotted name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            parts.reverse()
            return ".".join(parts)
        return None

    @staticmethod
    def _extract_calls_regex(code: str) -> list[str]:
        """Fallback: extract method calls using regex."""
        # Match patterns like obj.Method(...) or Method(...)
        pattern = r"(?:(\w+)\.)?(\w+)\s*\("
        matches = re.findall(pattern, code)
        calls = []
        for obj, method in matches:
            if obj:
                calls.append(f"{obj}.{method}")
            else:
                calls.append(method)
        return calls
