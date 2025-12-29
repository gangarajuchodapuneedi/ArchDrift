"""Dependency graph builder for repository analysis.

This module builds a module-level dependency graph by scanning source files,
extracting relative imports, resolving them to target files, and mapping
both source and target files to modules.
"""

import ast
from pathlib import Path

from utils.architecture_config import ArchitectureConfig
from utils.architecture_mapper import map_path_to_module_id
from utils.deps_tsjs import extract_tsjs_import_specifiers
from utils.ts_import_resolver import resolve_tsjs_import
from utils.tsconfig_loader import find_tsconfig, load_tsconfig_compiler_options

# Directories to ignore during scanning
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "out",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
}

# Source file extensions to process
SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}


def _compute_python_search_roots(repo_root: Path) -> list[Path]:
    """Compute Python import search roots for absolute import resolution.
    
    Args:
        repo_root: Root directory of the repository.
        
    Returns:
        List of search root paths in order: [repo_root/src, repo_root] if src exists,
        otherwise [repo_root].
    """
    roots = []
    src_dir = repo_root / "src"
    if src_dir.exists() and src_dir.is_dir():
        roots.append(src_dir)
    roots.append(repo_root)
    return roots


def _detect_internal_python_prefixes(repo_root: Path) -> set[str]:
    """Detect internal Python top-level package prefixes from repository structure.
    
    Scans immediate child directories under repo_root/src (if exists) and repo_root
    to find top-level packages (directories containing at least one .py file).
    
    Args:
        repo_root: Root directory of the repository.
        
    Returns:
        Set of top-level package prefix strings.
    """
    prefixes: set[str] = set()
    
    # Check repo_root/src if it exists
    src_dir = repo_root / "src"
    if src_dir.exists() and src_dir.is_dir():
        for item in src_dir.iterdir():
            if item.is_dir():
                # Check if directory contains at least one .py file (recursively)
                if any(p.suffix == ".py" for p in item.rglob("*.py")):
                    prefixes.add(item.name)
    
    # Check immediate child directories under repo_root (non-src)
    for item in repo_root.iterdir():
        if item.is_dir() and item.name != "src":
            # Check if directory contains at least one .py file (recursively)
            if any(p.suffix == ".py" for p in item.rglob("*.py")):
                prefixes.add(item.name)
    
    return prefixes


def resolve_python_absolute_import(
    module_ref: str,
    search_roots: list[Path],
) -> Path | None:
    """Resolve a Python absolute import to a target file path.
    
    Args:
        module_ref: Absolute module reference (e.g., "mypkg.core", "mypkg.core.x").
        search_roots: List of root directories to search (in order).
        
    Returns:
        Path to the resolved target file, or None if not found.
    """
    # Convert module reference to path components
    # e.g., "mypkg.core.x" -> ["mypkg", "core", "x"]
    path_parts = module_ref.split(".")
    
    # Try each search root
    for root in search_roots:
        # Build target path: root / mypkg / core / x
        target = root
        for part in path_parts:
            target = target / part
        
        # Try candidates in order
        candidates = [
            target.with_suffix(".py"),
            target / "__init__.py",
        ]
        
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
    
    return None


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


def _parse_python_import_groups(
    source_text: str,
    internal_prefixes: set[str] | None,
) -> list[list[str]]:
    """Parse Python source code and generate import groups with ordered candidates.
    
    Each import statement yields a group (ordered list of candidates to try).
    For "from X import Y", tries X.Y first, then X.
    
    Args:
        source_text: Python source code as a string.
        internal_prefixes: Optional set of top-level package prefixes to consider as internal.
        
    Returns:
        List of import groups, where each group is a list of candidate module strings.
        
    Raises:
        ValueError: If source_text contains syntax errors.
    """
    try:
        tree = ast.parse(source_text)
    except SyntaxError as e:
        raise ValueError(f"Syntax error at line {e.lineno}: {e.msg}") from e
    
    groups: list[list[str]] = []
    
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
                        groups.append([module])
                # If internal_prefixes is None, exclude absolute imports
                # (relative imports are handled by ImportFrom)
        
        elif isinstance(node, ast.ImportFrom):
            # Handle: from a.b import c, from . import x, from ..pkg import y
            if node.level > 0:
                # Relative import - always include
                module_part = node.module or ""
                relative_module = "." * node.level + module_part
                groups.append([relative_module])
            else:
                # Absolute import: from X import Y
                if node.module is not None:
                    base = node.module  # e.g., "mypkg.core"
                    # Check if this is an internal import
                    if internal_prefixes is not None:
                        top_level = _top_level_name(base)
                        if top_level in internal_prefixes:
                            # Generate candidates: try submodules first, then base
                            candidates: list[str] = []
                            for alias in node.names:
                                if alias.name != "*":  # Skip wildcard imports
                                    # Try submodule first: X.Y
                                    candidates.append(f"{base}.{alias.name}")
                            # Then try base package: X
                            candidates.append(base)
                            if candidates:  # Only add if we have candidates
                                groups.append(candidates)
    
    return groups


def resolve_python_relative_import(file_path: Path, module_ref: str) -> Path | None:
    """Resolve a Python relative import to a target file path.

    Args:
        file_path: Path to the source file containing the import.
        module_ref: Relative module reference (e.g., ".", "..core", "...parent.child").

    Returns:
        Path to the resolved target file, or None if not found.
    """
    if not module_ref.startswith("."):
        return None

    # Count leading dots (level)
    level = 0
    for char in module_ref:
        if char == ".":
            level += 1
        else:
            break

    # Extract remainder (module part after dots)
    remainder = module_ref[level:]

    # Navigate up directory tree
    base_dir = file_path.parent
    ups = max(level - 1, 0)

    # Move up by ups levels
    target_dir = base_dir
    for _ in range(ups):
        if target_dir.parent == target_dir:
            # Reached root, cannot go up further
            return None
        target_dir = target_dir.parent

    # Build target path
    if remainder:
        # Replace dots with slashes for module path
        module_path = remainder.replace(".", "/")
        target = target_dir / module_path
    else:
        target = target_dir

    # Try candidates in order
    candidates = [
        target.with_suffix(".py"),
        target / "__init__.py",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def resolve_tsjs_relative_import(file_path: Path, spec: str) -> Path | None:
    """Resolve a JS/TS relative import specifier to a target file path.

    Args:
        file_path: Path to the source file containing the import.
        spec: Relative import specifier (e.g., "./x", "../y", ".").

    Returns:
        Path to the resolved target file, or None if not found.
    """
    if not spec.startswith("."):
        return None

    # Resolve relative to file's directory
    base = file_path.parent / spec

    # If base has extension and exists, return it
    if base.suffix and base.exists() and base.is_file():
        return base

    # Try candidates in order
    candidates = [
        base.with_suffix(".ts"),
        base.with_suffix(".tsx"),
        base.with_suffix(".js"),
        base.with_suffix(".jsx"),
        base / "index.ts",
        base / "index.tsx",
        base / "index.js",
        base / "index.jsx",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def build_dependency_graph(
    repo_root: Path,
    config: ArchitectureConfig,
    *,
    max_files: int = 2000,
    max_file_bytes: int = 200_000,
    max_evidence: int = 200,
) -> dict:
    """Build a module-level dependency graph from repository source files.

    Scans the repository for source files, extracts relative imports, resolves
    them to target files, and maps both source and target files to modules to
    create a dependency graph.

    Args:
        repo_root: Root directory of the repository to scan.
        config: ArchitectureConfig containing module mapping configuration.
        max_files: Maximum number of files to scan (default: 2000).
        max_file_bytes: Maximum file size in bytes to read (default: 200_000).
        max_evidence: Maximum number of evidence items to collect (default: 200).

    Returns:
        Dictionary containing:
        - repo_root: Repository root path as string
        - scanned_files: Number of files scanned
        - included_files: Number of files successfully processed
        - skipped_files: Number of files skipped (size limit, read errors)
        - unmapped_files: Number of files that mapped to unmapped_module_id
        - edges: List of unique edges [{"from": "A", "to": "B"}, ...] (sorted)
        - evidence: List of evidence items (bounded by max_evidence)
        - unresolved_imports: Number of imports that could not be resolved

    Raises:
        ValueError: If repo_root does not exist or is not a directory.
    """
    # Validate repo_root
    if not repo_root.exists():
        raise ValueError(f"Repository root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"Repository root is not a directory: {repo_root}")

    # Load ts/js config once
    tsconfig = None
    tsconfig_path = find_tsconfig(repo_root)
    if tsconfig_path:
        tsconfig = load_tsconfig_compiler_options(tsconfig_path)
    
    # Compute Python import search roots and internal prefixes
    python_search_roots = _compute_python_search_roots(repo_root)
    python_internal_prefixes = _detect_internal_python_prefixes(repo_root)

    # Find candidate source files
    candidate_files: list[Path] = []

    def should_ignore_dir(path: Path) -> bool:
        """Check if a directory should be ignored."""
        return path.name in IGNORE_DIRS

    def collect_files(path: Path):
        """Recursively collect source files."""
        if should_ignore_dir(path):
            return

        try:
            for item in path.iterdir():
                if item.is_dir():
                    collect_files(item)
                elif item.is_file() and item.suffix in SOURCE_EXTENSIONS:
                    candidate_files.append(item)
        except PermissionError:
            # Skip directories we can't access
            pass

    collect_files(repo_root)

    # Sort by repo-relative POSIX path
    def get_repo_relative_posix(path: Path) -> str:
        """Get repo-relative POSIX path string."""
        try:
            rel_path = path.relative_to(repo_root)
            return str(rel_path.as_posix())
        except ValueError:
            # Path not relative to repo_root, use full path
            return str(path.as_posix())

    candidate_files.sort(key=get_repo_relative_posix)

    # Apply max_files limit
    files_to_scan = candidate_files[:max_files]

    # Statistics
    scanned_files = len(files_to_scan)
    included_files = 0
    skipped_files = 0
    unmapped_files = 0
    unresolved_imports = 0
    bucket_counts: dict[str, int] = {}

    # Graph data structures
    edges_set: set[tuple[str, str]] = set()
    evidence_list: list[dict] = []

    # Process each file
    for file_path in files_to_scan:
        # Get repo-relative path
        try:
            rel_path = file_path.relative_to(repo_root)
            rel_path_str = str(rel_path.as_posix())
        except ValueError:
            rel_path_str = str(file_path.as_posix())

        # Read file
        try:
            file_size = file_path.stat().st_size
            if file_size > max_file_bytes:
                skipped_files += 1
                continue

            source_text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            skipped_files += 1
            continue

        included_files += 1

        # Map file to module
        from_module = map_path_to_module_id(rel_path_str, config)
        if from_module == config.unmapped_module_id:
            unmapped_files += 1
            # Still continue to scan imports (but won't create edges)
            parts = rel_path_str.split("/")
            if len(parts) >= 2:
                bucket = "/".join(parts[:2])
            elif len(parts) == 1 and parts[0]:
                bucket = parts[0]
            else:
                bucket = "."

            if bucket in bucket_counts:
                bucket_counts[bucket] += 1
            elif len(bucket_counts) < 200:
                bucket_counts[bucket] = 1
            else:
                bucket_counts["__other__"] = bucket_counts.get("__other__", 0) + 1

        # Extract imports based on file extension
        lang: str | None = None

        if file_path.suffix == ".py":
            lang = "py"
            try:
                # Parse Python imports into groups with ordered candidates
                import_groups = _parse_python_import_groups(source_text, python_internal_prefixes)
            except Exception:
                # Skip if extraction fails
                continue
            
            # Process each import group
            for group in import_groups:
                resolved_path = None
                # Try candidates in order
                for import_ref in group:
                    if import_ref.startswith("."):
                        # Relative import
                        resolved_path = resolve_python_relative_import(file_path, import_ref)
                    else:
                        # Absolute import
                        resolved_path = resolve_python_absolute_import(import_ref, python_search_roots)
                    
                    if resolved_path is not None:
                        # Found a match, use it
                        break
                
                if resolved_path is None:
                    # None of the candidates resolved
                    unresolved_imports += 1
                    continue
                
                # Map target file to module
                try:
                    rel_target = resolved_path.relative_to(repo_root)
                    rel_target_str = str(rel_target.as_posix())
                except ValueError:
                    unresolved_imports += 1
                    continue
                
                to_module = map_path_to_module_id(rel_target_str, config)
                
                # Add edge only if both modules are mapped and different
                if (
                    from_module != config.unmapped_module_id
                    and to_module != config.unmapped_module_id
                    and from_module != to_module
                ):
                    edge = (from_module, to_module)
                    edges_set.add(edge)
                    
                    # Add evidence (bounded)
                    if len(evidence_list) < max_evidence:
                        evidence_list.append(
                            {
                                "from_file": rel_path_str,
                                "to_file": rel_target_str,
                                "import_ref": group[0],  # Use first candidate for display
                                "from_module": from_module,
                                "to_module": to_module,
                                "lang": lang,
                            }
                        )
        
        elif file_path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            lang = "tsjs"
            imports = extract_tsjs_import_specifiers(
                source_text, internal_prefixes=None, include_absolute=True
            )
            
            # Process each import
            for import_ref in imports:
                # Resolve import to target file
                if import_ref.startswith("."):
                    resolved_path = resolve_tsjs_relative_import(file_path, import_ref)
                else:
                    if tsconfig is None:
                        # No tsconfig/jsconfig: skip absolute/bare specs to keep old behaviour
                        continue
                    resolved_path = resolve_tsjs_import(
                        file_path=file_path,
                        spec=import_ref,
                        repo_root=repo_root,
                        tsconfig=tsconfig,
                    )

                if resolved_path is None:
                    unresolved_imports += 1
                    continue

                # Map target file to module
                try:
                    rel_target = resolved_path.relative_to(repo_root)
                    rel_target_str = str(rel_target.as_posix())
                except ValueError:
                    unresolved_imports += 1
                    continue

                to_module = map_path_to_module_id(rel_target_str, config)

                # Add edge only if both modules are mapped and different
                if (
                    from_module != config.unmapped_module_id
                    and to_module != config.unmapped_module_id
                    and from_module != to_module
                ):
                    edge = (from_module, to_module)
                    edges_set.add(edge)

                    # Add evidence (bounded)
                    if len(evidence_list) < max_evidence:
                        evidence_list.append(
                            {
                                "from_file": rel_path_str,
                                "to_file": rel_target_str,
                                "import_ref": import_ref,
                                "from_module": from_module,
                                "to_module": to_module,
                                "lang": lang,
                            }
                        )

    # Convert edges to sorted list
    edges = [{"from": from_mod, "to": to_mod} for from_mod, to_mod in sorted(edges_set)]

    unmapped_buckets = sorted(bucket_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    unmapped_bucket_list = [{"bucket": b, "count": c} for b, c in unmapped_buckets]

    return {
        "repo_root": str(repo_root),
        "scanned_files": scanned_files,
        "included_files": included_files,
        "skipped_files": skipped_files,
        "unmapped_files": unmapped_files,
        "edges": edges,
        "evidence": evidence_list,
        "unresolved_imports": unresolved_imports,
        "unmapped_buckets": unmapped_bucket_list,
    }

