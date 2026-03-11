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

    Only inspects DIRECT method calls on known Resolve object variables.
    Calls on return values (e.g., folder.GetName().upper()) are not checked —
    only folder.GetName() is validated.
    """

    # Variable names that are known to hold Resolve API objects.
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
        self.valid_methods = valid_methods
        self._method_names_only = {m.split(".")[-1] for m in valid_methods}

    def validate(self, code: str) -> ValidationResult:
        """
        Validate generated code against the API whitelist.

        Only checks DIRECT method calls on known Resolve object variables.
        e.g., folder.GetName() is checked, but folder.GetName().upper() is not.
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
        Extract DIRECT method calls on Resolve object variables using AST.

        Only matches patterns like:
            resolve_var.Method(...)
        NOT:
            resolve_var.Method().something_else(...)
        """
        tree = ast.parse(code)
        calls = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue

            method_name = node.func.attr
            value = node.func.value

            # Direct call on a variable: var.Method(...)
            if isinstance(value, ast.Name) and value.id in self.RESOLVE_OBJECT_VARS:
                calls.append((value.id, method_name))

        return calls

    def _extract_resolve_calls_regex(self, code: str) -> list[tuple[str, str]]:
        """Fallback: extract direct Resolve API calls using regex."""
        # Match var.Method( but NOT var.Method().something(
        pattern = r"\b(\w+)\.(\w+)\s*\("
        matches = re.findall(pattern, code)
        calls = []
        for obj, method in matches:
            if obj in self.RESOLVE_OBJECT_VARS:
                calls.append((obj, method))
        return calls
