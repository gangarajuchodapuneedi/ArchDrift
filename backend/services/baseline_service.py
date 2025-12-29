"""Baseline generator service for creating dependency graph snapshots.

This module provides functions to generate baselines by loading architecture
configuration, building the current dependency graph from a repository folder,
and storing it with a stable repo_id-based directory structure.
"""

import hashlib
from pathlib import Path

from utils.architecture_config import load_architecture_config
from utils.baseline_store import (
    get_active_exceptions,
    load_baseline,
    read_baseline_meta,
    store_baseline,
    write_baseline_exceptions,
    write_baseline_meta,
)
from utils.dependency_graph import build_dependency_graph


def compute_repo_id(repo_root: Path) -> str:
    """Compute a stable repository ID from the repository root path.

    Args:
        repo_root: Root directory of the repository.

    Returns:
        16-character hexadecimal repository ID.

    Raises:
        ValueError: If repo_root does not exist or is not a directory.
    """
    if not repo_root.exists():
        raise ValueError(f"Repository root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"Repository root is not a directory: {repo_root}")

    # Use resolved POSIX path as canonical identity
    canonical_path = repo_root.resolve().as_posix()

    # Compute SHA-256 hash
    hash_obj = hashlib.sha256(canonical_path.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()

    # Return first 16 hex characters
    return hash_hex[:16]


def default_data_dir() -> Path:
    """Get the default data directory for storing baselines.

    Returns:
        Path to backend/data directory.
    """
    backend_dir = Path(__file__).resolve().parents[1]
    return backend_dir / "data"


def baseline_dir_for_repo(repo_root: Path, data_dir: Path | None = None) -> Path:
    """Get the baseline directory path for a repository.

    Args:
        repo_root: Root directory of the repository.
        data_dir: Optional data directory. If None, uses default_data_dir().

    Returns:
        Path to baseline directory: data_dir/baselines/<repo_id>/
    """
    if data_dir is None:
        data_dir = default_data_dir()

    repo_id = compute_repo_id(repo_root)
    return data_dir / "baselines" / repo_id


def generate_baseline(
    repo_root: Path,
    *,
    config_dir: Path | None = None,
    data_dir: Path | None = None,
    max_files: int = 2000,
    max_file_bytes: int = 200_000,
) -> dict:
    """Generate a baseline snapshot of the current dependency graph.

    Loads architecture configuration, builds the dependency graph from the
    repository folder, and stores it as a baseline with a stable repo_id-based
    directory structure.

    Args:
        repo_root: Root directory of the repository to analyze.
        config_dir: Optional directory containing architecture config files.
            If None, uses default backend/architecture directory.
        data_dir: Optional data directory for storing baselines.
            If None, uses default backend/data directory.
        max_files: Maximum number of files to scan (default: 2000).
        max_file_bytes: Maximum file size in bytes to read (default: 200_000).

    Returns:
        Dictionary containing:
        - repo_id: 16-character hexadecimal repository ID
        - baseline_dir: Path to baseline directory as string
        - baseline_hash_sha256: 64-character SHA-256 hash of baseline edges
        - edge_count: Number of edges in baseline
        - scanned_files: Number of files scanned
        - included_files: Number of files successfully processed
        - skipped_files: Number of files skipped
        - unmapped_files: Number of files that mapped to unmapped_module_id
        - unresolved_imports: Number of imports that could not be resolved

    Raises:
        ValueError: If repo_root is invalid, config loading fails, or integrity check fails.
    """
    # Load architecture configuration
    config = load_architecture_config(config_dir)

    # Build current dependency graph
    graph = build_dependency_graph(
        repo_root, config, max_files=max_files, max_file_bytes=max_file_bytes
    )

    # Extract edges (already unique and sorted from build_dependency_graph)
    edges = graph["edges"]

    # Compute baseline directory
    baseline_dir = baseline_dir_for_repo(repo_root, data_dir=data_dir)

    # Store baseline
    health_stats = {
        "included_files": graph.get("included_files", 0),
        "unmapped_files": graph.get("unmapped_files", 0),
        "unresolved_imports": graph.get("unresolved_imports", 0),
        "unmapped_buckets": graph.get("unmapped_buckets", []),
    }

    store_result = store_baseline(baseline_dir, edges, graph_stats=health_stats)

    # Integrity check: load and verify hash matches
    loaded = load_baseline(baseline_dir)
    if loaded["summary"]["baseline_hash_sha256"] != store_result["baseline_hash_sha256"]:
        raise ValueError(
            f"Baseline integrity check failed: stored hash {store_result['baseline_hash_sha256']} "
            f"does not match loaded hash {loaded['summary']['baseline_hash_sha256']}"
        )

    # Compute repo_id
    repo_id = compute_repo_id(repo_root)

    # Return result dict
    return {
        "repo_id": repo_id,
        "baseline_dir": str(baseline_dir),
        "baseline_hash_sha256": store_result["baseline_hash_sha256"],
        "edge_count": store_result["edge_count"],
        "scanned_files": graph["scanned_files"],
        "included_files": graph["included_files"],
        "skipped_files": graph["skipped_files"],
        "unmapped_files": graph["unmapped_files"],
        "unresolved_imports": graph["unresolved_imports"],
    }


def get_baseline_status(repo_root: Path, data_dir: Path | None = None) -> dict:
    """Get the status of a baseline for a repository (read-only).

    Checks if a baseline exists and returns its status without regenerating it.

    Args:
        repo_root: Root directory of the repository.
        data_dir: Optional data directory. If None, uses default_data_dir().

    Returns:
        Dictionary containing:
        - exists: bool indicating if baseline exists
        - status: "draft" if exists, "missing" if not
        - baseline_hash_sha256: Hash if exists, None otherwise
        - summary: Full summary dict if exists, None otherwise

    Raises:
        ValueError: If repo_root is invalid.
    """
    # Compute baseline directory
    baseline_dir = baseline_dir_for_repo(repo_root, data_dir=data_dir)

    # Check if baseline_summary.json exists
    summary_path = baseline_dir / "baseline_summary.json"
    if not summary_path.exists():
        return {
            "exists": False,
            "status": "missing",
            "baseline_hash_sha256": None,
            "summary": None,
        }

    # Load baseline summary (read-only, no validation needed for status check)
    try:
        import json

        with open(summary_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
    except Exception:
        # If we can't read it, treat as missing
        return {
            "exists": False,
            "status": "missing",
            "baseline_hash_sha256": None,
            "summary": None,
        }

    # Read baseline metadata if exists
    meta_data = read_baseline_meta(baseline_dir)
    baseline_hash = summary_data.get("baseline_hash_sha256")

    # Determine status from meta if available, otherwise default to "draft"
    if meta_data and meta_data.get("status") == "accepted":
        status = "accepted"
        approved_by = meta_data.get("approved_by")
        approved_at = meta_data.get("approved_at")
    else:
        status = "draft"
        approved_by = None
        approved_at = None

    # Get active exceptions count
    active_exceptions = get_active_exceptions(baseline_dir)
    active_exceptions_count = len(active_exceptions)

    health_summary = summary_data.get("health") if isinstance(summary_data, dict) else None
    baseline_health = None
    if isinstance(health_summary, dict):
        edge_count = health_summary.get("edge_count", 0)
        included_files = health_summary.get("included_files", 0)
        unmapped_files = health_summary.get("unmapped_files", 0)
        unmapped_ratio = float(health_summary.get("unmapped_ratio", 0.0))
        unresolved_imports = health_summary.get("unresolved_imports", 0)
        top_buckets = health_summary.get("top_unmapped_buckets", [])

        baseline_ready = edge_count > 0
        mapping_ready = included_files > 0 and unmapped_ratio < 0.50

        next_actions: list[str] = []
        if edge_count == 0:
            next_actions.append(
                "Update module_map.json to cover your real source roots (e.g., src/, packages/) and regenerate baseline."
            )
        if unmapped_ratio >= 0.50:
            bucket_labels = ", ".join([b["bucket"] for b in top_buckets[:3] if isinstance(b, dict) and "bucket" in b])
            if bucket_labels:
                next_actions.append(
                    f"Reduce unmapped files by adding/adjusting module_map.json prefixes for these buckets: {bucket_labels}."
                )
            else:
                next_actions.append(
                    "Reduce unmapped files by adding/adjusting module_map.json prefixes for the largest unmapped folders."
                )
        if included_files == 0:
            next_actions.append(
                "No source files were included. Check scan limits / repo path / file extensions."
            )
        if unresolved_imports and unresolved_imports > 0:
            next_actions.append(
                "Resolve TS/JS alias imports via tsconfig paths/baseUrl (MT_22) or add mapping for alias roots."
            )

        baseline_health = {
            "baseline_ready": baseline_ready,
            "mapping_ready": mapping_ready,
            "edge_count": edge_count,
            "included_files": included_files,
            "unmapped_files": unmapped_files,
            "unmapped_ratio": unmapped_ratio,
            "unresolved_imports": unresolved_imports,
            "top_unmapped_buckets": top_buckets[:10] if isinstance(top_buckets, list) else [],
            "next_actions": next_actions[:5],
        }

    return {
        "exists": True,
        "status": status,
        "baseline_hash_sha256": baseline_hash,
        "summary": summary_data,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "active_exceptions_count": active_exceptions_count,
        "baseline_health": baseline_health,
    }


def approve_baseline(
    repo_root: Path,
    approved_by: str,
    approval_note: str | None = None,
    exceptions: list[dict] | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Approve a baseline and optionally add exceptions.

    Args:
        repo_root: Root directory of the repository.
        approved_by: Name or email of the approver.
        approval_note: Optional approval note.
        exceptions: Optional list of exception dictionaries to add.
        data_dir: Optional data directory. If None, uses default_data_dir().

    Returns:
        Dictionary containing:
        - status: "accepted"
        - approved_by: Name of approver
        - approved_at: ISO 8601 UTC timestamp
        - baseline_hash_sha256: Baseline hash
        - active_exceptions_count: Number of active exceptions

    Raises:
        ValueError: If repo_root is invalid, baseline doesn't exist, or exception validation fails.
    """
    from datetime import datetime, timezone

    # Check if baseline exists
    status_result = get_baseline_status(repo_root, data_dir=data_dir)
    if not status_result["exists"]:
        raise ValueError("Baseline does not exist. Generate baseline before approving.")

    # Get baseline directory and hash
    baseline_dir = baseline_dir_for_repo(repo_root, data_dir=data_dir)
    baseline_hash = status_result["baseline_hash_sha256"]
    if baseline_hash is None:
        raise ValueError("Baseline hash not found in summary")

    # Write approval metadata
    approved_at = datetime.now(timezone.utc).isoformat()
    write_baseline_meta(
        baseline_dir,
        status="accepted",
        approved_by=approved_by,
        approved_at=approved_at,
        approval_note=approval_note,
        baseline_hash=baseline_hash,
    )

    # Write exceptions if provided
    if exceptions is not None:
        write_baseline_exceptions(baseline_dir, exceptions)

    # Get active exceptions count
    active_exceptions = get_active_exceptions(baseline_dir)
    active_exceptions_count = len(active_exceptions)

    return {
        "status": "accepted",
        "approved_by": approved_by,
        "approved_at": approved_at,
        "baseline_hash_sha256": baseline_hash,
        "active_exceptions_count": active_exceptions_count,
    }

