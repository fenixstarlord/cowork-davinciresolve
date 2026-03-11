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
    """Validates generated code against a whitelist of known Resolve API methods.

    Only inspects calls made on known Resolve object variables. Standard Python
    code (builtins, string methods, list ops, etc.) is never flagged.
    """

    # Variable names that are known to hold Resolve API objects.
    # If a method is called on one of these, it must be in the whitelist.
    RESOLVE_OBJECT_VARS = {
        "resolve", "project_manager", "pm", "project", "media_storage",
        "media_pool", "media_pool_item", "clip", "item", "folder",
        "root_folder", "timeline", "timeline_item", "gallery",
        "gallery_still", "gallery_still_album", "color_group", "fusion",
        "footage_folder", "timelines_folder", "current_folder",
        "broadcast_timeline", "web_timeline", "comp", "fusion_comp",
        "media_pool_folder",
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

        Only checks method calls on known Resolve object variables.
        Regular Python code is allowed through without validation.
        """
        invalid_calls = []
        warnings = []

        try:
            resolve_calls = self._extract_resolve_calls_ast(code)
        except SyntaxError:
            resolve_calls = self._extract_resolve_calls_regex(code)
            warnings.append("Code has syntax errors; used regex-based validation (less accurate).")

        for obj_var, method_name in resolve_calls:
            if method_name not in self._method_names_only:
                invalid_calls.append(f"{obj_var}.{method_name}")

        return ValidationResult(
            is_valid=len(invalid_calls) == 0,
            invalid_calls=invalid_calls,
            warnings=warnings,
        )

    def _extract_resolve_calls_ast(self, code: str) -> list[tuple[str, str]]:
        """
        Extract method calls on Resolve objects using AST parsing.

        Returns list of (object_variable, method_name) tuples for calls made
        on known Resolve object variables.
        """
        tree = ast.parse(code)
        calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                # Get the root variable name of the call chain
                root_var = self._get_root_var(node.func.value)
                if root_var and root_var in self.RESOLVE_OBJECT_VARS:
                    calls.append((root_var, method_name))

        return calls

    @staticmethod
    def _get_root_var(node) -> str | None:
        """Walk down the attribute chain to find the root variable name."""
        current = node
        while isinstance(current, ast.Attribute):
            current = current.value
        if isinstance(current, ast.Name):
            return current.id
        # Handle calls like resolve.GetProjectManager().GetCurrentProject()
        if isinstance(current, ast.Call):
            if isinstance(current.func, ast.Attribute):
                return APIValidator._get_root_var(current.func.value)
            if isinstance(current.func, ast.Name):
                return current.func.id
        return None

    def _extract_resolve_calls_regex(self, code: str) -> list[tuple[str, str]]:
        """Fallback: extract Resolve API calls using regex."""
        pattern = r"\b(\w+)\.(\w+)\s*\("
        matches = re.findall(pattern, code)
        calls = []
        for obj, method in matches:
            if obj in self.RESOLVE_OBJECT_VARS:
                calls.append((obj, method))
        return calls
