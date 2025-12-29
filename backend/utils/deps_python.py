"""Python import dependency extractor.

This module extracts imported module references from Python source code
using AST parsing. It supports both absolute and relative imports, and
can filter imports based on internal package prefixes.
"""

import ast


def _top_level_name(module: str) -> str:
    """Extract the top-level package name from a module string.

    Args:
        module: Module string (e.g., "a.b", ".x.y", "..x").

    Returns:
        Top-level package name. Returns "" if cannot determine.
    """
    if not module:
        return ""

    # Skip leading dots for relative imports
    module_clean = module.lstrip(".")

    if not module_clean:
        return ""

    # Extract first component (top-level package)
    parts = module_clean.split(".", 1)
    return parts[0]


def extract_python_import_modules(
    source_text: str,
    *,
    internal_prefixes: set[str] | None = None,
) -> list[str]:
    """Extract imported module references from Python source code.

    Parses the source code using AST and extracts all import statements,
    filtering them based on internal_prefixes rules:
    - Relative imports (level > 0) are always included
    - Absolute imports are included only if internal_prefixes is provided
      and the top-level package matches one of the prefixes
    - If internal_prefixes is None, only relative imports are included

    Args:
        source_text: Python source code as a string.
        internal_prefixes: Optional set of top-level package prefixes to
            consider as internal. If None, only relative imports are included.

    Returns:
        Sorted list of unique module reference strings.

    Raises:
        ValueError: If source_text contains syntax errors. The error message
            includes the line number and error text.
    """
    # Parse the source code
    try:
        tree = ast.parse(source_text)
    except SyntaxError as e:
        raise ValueError(
            f"Syntax error at line {e.lineno}: {e.msg}"
        ) from e

    # Collect all import modules
    modules: set[str] = set()

    # Walk the AST to find import nodes
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # Handle: import a, import a.b, import a as b
            for alias in node.names:
                module = alias.name  # e.g., "a" or "a.b"
                # Check if this is an internal import
                if internal_prefixes is not None:
                    top_level = _top_level_name(module)
                    if top_level in internal_prefixes:
                        modules.add(module)
                # If internal_prefixes is None, exclude absolute imports
                # (relative imports are handled by ImportFrom)

        elif isinstance(node, ast.ImportFrom):
            # Handle: from a.b import c, from . import x, from ..pkg import y
            if node.level > 0:
                # Relative import - always include
                module_part = node.module or ""
                relative_module = "." * node.level + module_part
                modules.add(relative_module)
            else:
                # Absolute import
                if node.module is not None:
                    module = node.module  # e.g., "a.b"
                    # Check if this is an internal import
                    if internal_prefixes is not None:
                        top_level = _top_level_name(module)
                        if top_level in internal_prefixes:
                            modules.add(module)
                    # If internal_prefixes is None, exclude absolute imports

    # Return sorted, deduplicated list
    return sorted(modules)

