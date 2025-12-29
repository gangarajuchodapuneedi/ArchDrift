"""JavaScript/TypeScript import dependency extractor.

This module extracts imported module specifiers from JavaScript/TypeScript
source code using regex parsing. It supports ESM imports, CommonJS require,
dynamic imports, and export-from statements, with comment stripping and
internal prefix filtering.
"""

import re


def strip_tsjs_comments_preserve_strings(text: str) -> str:
    """Strip comments from JS/TS source while preserving string literals.

    Uses a state machine to remove line comments (//) and block comments (/* */)
    while preserving string content in single quotes, double quotes, and
    template strings.

    Args:
        text: JavaScript/TypeScript source code.

    Returns:
        Source code with comments removed (replaced with spaces).
    """
    result = []
    i = 0
    state = "normal"

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if state == "normal":
            if char == "/" and next_char == "/":
                # Start of line comment
                result.append(" ")
                i += 1
                state = "line_comment"
            elif char == "/" and next_char == "*":
                # Start of block comment
                result.append(" ")
                i += 1
                state = "block_comment"
            elif char == "'":
                result.append(char)
                state = "single_quote"
            elif char == '"':
                result.append(char)
                state = "double_quote"
            elif char == "`":
                result.append(char)
                state = "template"
            else:
                result.append(char)

        elif state == "line_comment":
            if char == "\n":
                result.append(char)
                state = "normal"
            else:
                result.append(" ")

        elif state == "block_comment":
            if char == "*" and next_char == "/":
                result.append(" ")
                i += 1
                state = "normal"
            else:
                result.append(" ")

        elif state == "single_quote":
            result.append(char)
            if char == "\\":
                # Escape sequence - skip next char
                if i + 1 < len(text):
                    i += 1
                    result.append(text[i])
            elif char == "'":
                state = "normal"

        elif state == "double_quote":
            result.append(char)
            if char == "\\":
                # Escape sequence - skip next char
                if i + 1 < len(text):
                    i += 1
                    result.append(text[i])
            elif char == '"':
                state = "normal"

        elif state == "template":
            result.append(char)
            if char == "\\":
                # Escape sequence - skip next char
                if i + 1 < len(text):
                    i += 1
                    result.append(text[i])
            elif char == "`":
                state = "normal"

        i += 1

    return "".join(result)


def _top_level_specifier(spec: str) -> str:
    """Extract the top-level specifier from an import specifier.

    Args:
        spec: Import specifier (e.g., "myapp/core", "@acme/ui/button", "./local").

    Returns:
        Top-level specifier. For scoped packages, returns "@scope/name".
        For regular packages, returns first segment. Returns "" if cannot determine.
    """
    if not spec:
        return ""

    # Strip leading dots and slashes only for absolute specifiers
    # (don't break relative specifiers)
    if spec.startswith("."):
        # Relative specifier - return empty (shouldn't be used for filtering)
        return ""

    # Handle scoped packages (@scope/name)
    if spec.startswith("@"):
        parts = spec.split("/", 2)
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return spec

    # Regular package - return first segment before "/"
    parts = spec.split("/", 1)
    return parts[0]


def extract_tsjs_import_specifiers(
    source_text: str,
    *,
    internal_prefixes: set[str] | None = None,
    include_absolute: bool = False,
) -> list[str]:
    """Extract imported module specifiers from JavaScript/TypeScript source code.

    Parses the source code using regex and extracts all import specifiers from:
    - ESM imports: `import ... from "spec"` or `import "spec"`
    - Export-from: `export ... from "spec"`
    - CommonJS require: `require("spec")`
    - Dynamic import: `import("spec")`

    Filters them based on internal_prefixes/include_absolute rules:
    - Relative specifiers (start with ".") are always included
    - Absolute specifiers are included if include_absolute is True
    - Otherwise, absolute specifiers are included only when
      internal_prefixes is provided and the top-level specifier matches
      one of the prefixes
    - If internal_prefixes is None and include_absolute is False, only
      relative specifiers are included

    Args:
        source_text: JavaScript/TypeScript source code as a string.
        internal_prefixes: Optional set of top-level specifier prefixes to
            consider as internal. If None and include_absolute is False,
            only relative specifiers are included.
        include_absolute: If True, include all absolute specifiers in the
            output (in addition to relative).

    Returns:
        Sorted list of unique import specifier strings.
    """
    # Strip comments first
    text = strip_tsjs_comments_preserve_strings(source_text)

    # Collect all import specifiers
    specifiers: set[str] = set()

    # Pattern for ESM import (not dynamic import)
    # Match: import ... from "spec" or import "spec"
    # Avoid matching: import("spec")
    esm_pattern = r'import\s+(?:[^"\'()]*from\s+)?["\']([^"\']+)["\']'
    for match in re.finditer(esm_pattern, text, re.MULTILINE):
        # Check that this is not a dynamic import
        # Look backwards to see if there's an opening parenthesis
        start_pos = match.start()
        # Check if there's "import(" before this (with optional whitespace)
        before_text = text[max(0, start_pos - 10) : start_pos]
        if not re.search(r'import\s*\(', before_text):
            spec = match.group(1)
            # Filter by internal_prefixes
            if spec.startswith("."):
                # Relative - always include
                specifiers.add(spec)
            elif include_absolute:
                specifiers.add(spec)
            elif internal_prefixes is not None:
                top_level = _top_level_specifier(spec)
                if top_level in internal_prefixes:
                    specifiers.add(spec)
                # If internal_prefixes is None, exclude absolute imports

    # Pattern for export-from
    export_pattern = r'export\s+[^"\']*from\s+["\']([^"\']+)["\']'
    for match in re.finditer(export_pattern, text, re.MULTILINE):
        spec = match.group(1)
        # Filter by internal_prefixes
        if spec.startswith("."):
            # Relative - always include
            specifiers.add(spec)
        elif include_absolute:
            specifiers.add(spec)
        elif internal_prefixes is not None:
            top_level = _top_level_specifier(spec)
            if top_level in internal_prefixes:
                specifiers.add(spec)

    # Pattern for require()
    require_pattern = r'require\s*\(\s*["\']([^"\']+)["\']\s*\)'
    for match in re.finditer(require_pattern, text, re.MULTILINE):
        spec = match.group(1)
        # Filter by internal_prefixes
        if spec.startswith("."):
            # Relative - always include
            specifiers.add(spec)
        elif include_absolute:
            specifiers.add(spec)
        elif internal_prefixes is not None:
            top_level = _top_level_specifier(spec)
            if top_level in internal_prefixes:
                specifiers.add(spec)

    # Pattern for dynamic import()
    dynamic_pattern = r'import\s*\(\s*["\']([^"\']+)["\']\s*\)'
    for match in re.finditer(dynamic_pattern, text, re.MULTILINE):
        spec = match.group(1)
        # Filter by internal_prefixes
        if spec.startswith("."):
            # Relative - always include
            specifiers.add(spec)
        elif include_absolute:
            specifiers.add(spec)
        elif internal_prefixes is not None:
            top_level = _top_level_specifier(spec)
            if top_level in internal_prefixes:
                specifiers.add(spec)

    # Return sorted, deduplicated list
    return sorted(specifiers)

