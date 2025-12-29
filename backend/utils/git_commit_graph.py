"""Commit-level architecture delta extractor (no checkout).

Computes edge deltas for a commit versus its parent by reading blobs directly
from the Git object database. Only changed files are analyzed, bounded by
limits on file count and size. Skips binaries and non-source files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from git import Repo
NULL_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

from utils.architecture_config import ArchitectureConfig
from utils.architecture_mapper import map_path_to_module_id, normalize_repo_path
from utils.deps_python import extract_python_import_modules
from utils.deps_tsjs import extract_tsjs_import_specifiers

SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}


@dataclass
class Limits:
    max_changed_files: int = 200
    max_bytes_per_file: int = 200_000


def _is_binary(data: bytes) -> bool:
    return b"\0" in data


def _read_blob_text(tree, path: str, limits: Limits):
    """Read blob content from a tree respecting size/binary limits."""
    try:
        blob = tree / path
    except Exception:
        return None, "missing"
    try:
        stream = blob.data_stream
        data = stream.read(limits.max_bytes_per_file + 1)
    except Exception:
        return None, "read_error"

    if len(data) > limits.max_bytes_per_file:
        return None, "too_large"
    if _is_binary(data):
        return None, "binary"
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return None, "decode_error"
    return text, None


def _internal_prefixes_from_config(config: ArchitectureConfig) -> set[str]:
    """Derive internal prefixes from module roots (top-level segments)."""
    prefixes: set[str] = set()
    for module in config.modules:
        for root in module.roots:
            norm = normalize_repo_path(root)
            if "/" in norm:
                prefixes.add(norm.split("/", 1)[0])
            else:
                prefixes.add(norm)
    return prefixes


def _map_target_module(path_like: str, config: ArchitectureConfig) -> str:
    return map_path_to_module_id(path_like, config)


def _resolve_relative_path(file_path: str, import_spec: str, is_python: bool) -> str:
    """Resolve a relative import specifier to a repo-relative path string."""
    file_dir = Path(file_path).parent
    if is_python:
        # import_spec like ".core.svc" or "..pkg.mod"
        leading = 0
        for ch in import_spec:
            if ch == ".":
                leading += 1
            else:
                break
        remainder = import_spec[leading:]
        # For relative imports, level=leading dots, so move up (level-1) per Python semantics
        level = max(leading, 1)
        target_dir = file_dir
        for _ in range(level - 1):
            target_dir = target_dir.parent
        if remainder:
            target_rel = remainder.replace(".", "/")
            target_path = (target_dir / target_rel).as_posix()
        else:
            target_path = target_dir.as_posix()
        return normalize_repo_path(os.path.normpath(target_path))
    else:
        # JS/TS relative import like "./core/svc"
        target_path = (file_dir / import_spec).as_posix()
        return normalize_repo_path(os.path.normpath(target_path))


def _edges_from_text(
    file_path: str,
    text: str,
    config: ArchitectureConfig,
    prefixes: set[str],
) -> tuple[set[tuple[str, str]], list[dict]]:
    """Extract edges and evidence from source text."""
    ext = Path(file_path).suffix
    from_module = map_path_to_module_id(file_path, config)
    if from_module == config.unmapped_module_id:
        return set(), []

    edges: set[tuple[str, str]] = set()
    evidence: list[dict] = []

    if ext == ".py":
        imports = extract_python_import_modules(text, internal_prefixes=prefixes)
        for imp in imports:
            if imp.startswith("."):
                target_path = _resolve_relative_path(file_path, imp, is_python=True)
            else:
                target_path = normalize_repo_path(imp.replace(".", "/"))
            to_module = _map_target_module(target_path, config)
            if to_module == config.unmapped_module_id:
                continue
            edge = (from_module, to_module)
            edges.add(edge)
            evidence.append(
                {
                    "src_file": normalize_repo_path(file_path),
                    "import_text": imp,
                    "from_module": from_module,
                    "to_module": to_module,
                }
            )
    elif ext in {".js", ".jsx", ".ts", ".tsx"}:
        imports = extract_tsjs_import_specifiers(text, internal_prefixes=prefixes)
        for imp in imports:
            if imp.startswith("."):
                target_path = _resolve_relative_path(file_path, imp, is_python=False)
            else:
                target_path = normalize_repo_path(imp)
            to_module = _map_target_module(target_path, config)
            if to_module == config.unmapped_module_id:
                continue
            edge = (from_module, to_module)
            edges.add(edge)
            evidence.append(
                {
                    "src_file": normalize_repo_path(file_path),
                    "import_text": imp,
                    "from_module": from_module,
                    "to_module": to_module,
                }
            )

    return edges, evidence


def _collect_changed_files(commit, parent) -> list:
    """Return list of Diff objects for changed files between parent -> commit."""
    if parent is None:
        return list(commit.diff(NULL_TREE_SHA, create_patch=False))
    return list(parent.diff(commit, create_patch=False))


def build_commit_delta(
    repo_path: str,
    commit_sha: str,
    config: ArchitectureConfig,
    limits: Limits | None = None,
) -> dict:
    """Compute commit-level edge delta using blob reads only."""
    if limits is None:
        limits = Limits()

    repo = Repo(repo_path)
    commit = repo.commit(commit_sha)
    parent = commit.parents[0] if commit.parents else None

    prefixes = _internal_prefixes_from_config(config)

    diffs = _collect_changed_files(commit, parent)
    truncated = False
    if len(diffs) > limits.max_changed_files:
        diffs = diffs[: limits.max_changed_files]
        truncated = True

    edges_commit: set[tuple[str, str]] = set()
    edges_parent: set[tuple[str, str]] = set()
    evidence_commit: list[dict] = []
    evidence_parent: list[dict] = []

    stats = {
        "changed_files_considered": 0,
        "files_skipped_binary": 0,
        "files_skipped_too_large": 0,
    }

    for d in diffs:
        # Determine paths per side
        path_commit = d.b_path
        path_parent = d.a_path
        # Skip non-source extensions
        candidate_paths: Iterable[str] = [p for p in (path_commit, path_parent) if p]
        if not any(Path(p).suffix in SOURCE_EXTENSIONS for p in candidate_paths):
            continue

        stats["changed_files_considered"] += 1

        # Read commit side text if available
        commit_text = None
        if path_commit:
            text, reason = _read_blob_text(commit.tree, path_commit, limits)
            if text is None:
                if reason == "binary":
                    stats["files_skipped_binary"] += 1
                elif reason == "too_large":
                    stats["files_skipped_too_large"] += 1
            commit_text = text

        parent_text = None
        if parent is not None and path_parent:
            text, reason = _read_blob_text(parent.tree, path_parent, limits)
            if text is None:
                if reason == "binary":
                    stats["files_skipped_binary"] += 1
                elif reason == "too_large":
                    stats["files_skipped_too_large"] += 1
            parent_text = text

        # Extract edges
        if commit_text:
            e, ev = _edges_from_text(path_commit, commit_text, config, prefixes)
            edges_commit |= e
            evidence_commit.extend(ev)
        if parent_text:
            e, ev = _edges_from_text(path_parent, parent_text, config, prefixes)
            edges_parent |= e
            evidence_parent.extend(ev)

    edges_added = sorted(edges_commit - edges_parent, key=lambda t: (t[0], t[1]))
    edges_removed = sorted(edges_parent - edges_commit, key=lambda t: (t[0], t[1]))

    def _evidence_for(edges: list[tuple[str, str]], ev_pool: list[dict], direction: str):
        out: list[dict] = []
        for fr, to in edges:
            for ev in ev_pool:
                if ev["from_module"] == fr and ev["to_module"] == to:
                    out.append({**ev, "direction": direction})
        return out

    evidence = _evidence_for(edges_added, evidence_commit, "added") + _evidence_for(
        edges_removed, evidence_parent, "removed"
    )
    evidence.sort(
        key=lambda e: (
            e.get("src_file", ""),
            e.get("from_module", ""),
            e.get("to_module", ""),
            e.get("direction", ""),
            e.get("import_text", ""),
        )
    )

    return {
        "commit": commit.hexsha,
        "parent": parent.hexsha if parent else None,
        "edges_added": [{"from": fr, "to": to} for fr, to in edges_added],
        "edges_removed": [{"from": fr, "to": to} for fr, to in edges_removed],
        "edges_added_count": len(edges_added),
        "edges_removed_count": len(edges_removed),
        "evidence": evidence,
        "truncated": truncated,
        "stats": stats,
    }


    # NULL_TREE_SHA used for initial commit diff

