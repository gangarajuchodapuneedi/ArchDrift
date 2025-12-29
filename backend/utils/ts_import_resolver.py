"""Utilities to resolve TS/JS import specifiers using tsconfig paths/baseUrl."""

from __future__ import annotations

from pathlib import Path


TS_EXT_CANDIDATES = [
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
]


def _probe_tsjs_path(base: Path) -> Path | None:
    """Try file plus standard TS/JS extensions and index files."""
    if base.suffix and base.exists() and base.is_file():
        return base

    candidates = [
        base.with_suffix(ext) for ext in TS_EXT_CANDIDATES
    ] + [
        base / f"index{ext}" for ext in TS_EXT_CANDIDATES
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _resolve_tsjs_relative_import(file_path: Path, spec: str) -> Path | None:
    """Resolve relative TS/JS imports using existing probing rules."""
    if not spec.startswith("."):
        return None

    base = file_path.parent / spec
    return _probe_tsjs_path(base)


def match_tsconfig_paths(spec: str, paths_map: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Match spec against tsconfig paths; return list of (pattern, mapped)."""
    matches: list[tuple[int, list[tuple[str, str]]]] = []

    for pattern, targets in paths_map.items():
        if not isinstance(pattern, str) or not isinstance(targets, list):
            continue

        if "*" in pattern:
            if pattern.count("*") != 1:
                continue
            prefix, suffix = pattern.split("*", 1)
            if not spec.startswith(prefix) or not spec.endswith(suffix):
                continue
            wildcard_part = spec[len(prefix) : len(spec) - len(suffix)]
            mapped = []
            for target in targets:
                if isinstance(target, str):
                    mapped.append(target.replace("*", wildcard_part))
            matches.append((len(prefix), [(pattern, m) for m in mapped]))
        else:
            if spec != pattern:
                continue
            mapped = []
            for target in targets:
                if isinstance(target, str):
                    mapped.append(target)
            matches.append((len(pattern), [(pattern, m) for m in mapped]))

    if not matches:
        return []

    best_prefix = max(prefix for prefix, _ in matches)
    result: list[tuple[str, str]] = []
    for prefix_len, pairs in matches:
        if prefix_len == best_prefix:
            result.extend(pairs)
    return result


def resolve_ts_specifier_to_candidates(
    *,
    repo_root: Path,
    tsconfig: dict,
    spec: str,
) -> list[Path]:
    """Return candidate paths for a non-relative specifier using tsconfig."""
    if spec.startswith("."):
        return []

    tsconfig_dir = tsconfig.get("tsconfig_dir")
    if not isinstance(tsconfig_dir, Path):
        return []

    base_url = tsconfig.get("baseUrl")
    base_dir = tsconfig_dir / base_url if isinstance(base_url, str) else tsconfig_dir

    paths_map = tsconfig.get("paths") or {}
    candidates: list[Path] = []

    for _, mapped in match_tsconfig_paths(spec, paths_map):
        candidate = (base_dir / mapped).resolve()
        candidates.append(candidate)

    if isinstance(base_url, str):
        candidates.append((tsconfig_dir / base_url / spec).resolve())

    # Deduplicate while preserving order
    unique: list[Path] = []
    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key not in seen:
            seen.add(key)
            unique.append(cand)

    # Ensure within repo_root
    safe_candidates = []
    for cand in unique:
        try:
            cand.relative_to(repo_root.resolve())
        except ValueError:
            continue
        safe_candidates.append(cand)

    return safe_candidates


def resolve_tsjs_import(
    file_path: Path,
    spec: str,
    repo_root: Path,
    tsconfig: dict | None,
) -> Path | None:
    """Resolve relative or tsconfig-mapped TS/JS imports."""
    if spec.startswith("."):
        return _resolve_tsjs_relative_import(file_path, spec)

    if not tsconfig:
        return None

    for cand in resolve_ts_specifier_to_candidates(
        repo_root=repo_root, tsconfig=tsconfig, spec=spec
    ):
        resolved = _probe_tsjs_path(cand)
        if resolved:
            return resolved
    return None

