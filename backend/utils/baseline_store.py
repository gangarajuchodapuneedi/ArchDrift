"""Baseline storage utility for dependency graph snapshots.

This module provides functions to normalize edges, compute stable hashes,
store baseline files to disk, and load/validate them with tamper detection.
"""

import hashlib
import json
import os
import tempfile
from datetime import timezone
from pathlib import Path


def normalize_edges(edges: list[dict]) -> list[dict]:
    """Normalize a list of edges by validating, deduplicating, and sorting.

    Args:
        edges: List of edge dictionaries with "from" and "to" keys.

    Returns:
        Sorted list of unique edge dictionaries.

    Raises:
        ValueError: If any edge is missing "from" or "to", or if they are empty strings.
    """
    normalized: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"Edge at index {i} must be a dictionary, got {type(edge).__name__}")

        if "from" not in edge:
            raise ValueError(f"Edge at index {i} missing required key 'from'")
        if "to" not in edge:
            raise ValueError(f"Edge at index {i} missing required key 'to'")

        from_module = edge["from"]
        to_module = edge["to"]

        if not isinstance(from_module, str):
            raise ValueError(
                f"Edge at index {i} 'from' must be a string, got {type(from_module).__name__}"
            )
        if not isinstance(to_module, str):
            raise ValueError(
                f"Edge at index {i} 'to' must be a string, got {type(to_module).__name__}"
            )

        if not from_module:
            raise ValueError(f"Edge at index {i} 'from' must be non-empty")
        if not to_module:
            raise ValueError(f"Edge at index {i} 'to' must be non-empty")

        edge_tuple = (from_module, to_module)
        if edge_tuple not in seen:
            seen.add(edge_tuple)
            normalized.append({"from": from_module, "to": to_module})

    # Sort lexicographically by (from, to)
    normalized.sort(key=lambda e: (e["from"], e["to"]))

    return normalized


def canonical_edges_bytes(normalized_edges: list[dict]) -> bytes:
    """Create canonical JSON bytes representation of normalized edges.

    Args:
        normalized_edges: Already normalized and sorted list of edge dictionaries.

    Returns:
        UTF-8 encoded bytes of canonical JSON representation.
    """
    payload = {"version": "1.0", "edges": normalized_edges}
    json_str = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return json_str.encode("utf-8")


def compute_baseline_hash_sha256(normalized_edges: list[dict]) -> str:
    """Compute SHA-256 hash of normalized edges.

    Args:
        normalized_edges: Already normalized and sorted list of edge dictionaries.

    Returns:
        64-character hexadecimal hash string.
    """
    canonical_bytes = canonical_edges_bytes(normalized_edges)
    hash_obj = hashlib.sha256(canonical_bytes)
    return hash_obj.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write text to a file.

    Creates parent directories if needed, writes to a temporary file first,
    then atomically replaces the target file.

    Args:
        path: Target file path.
        text: Text content to write.
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file in same directory
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.write(text)

    # Atomically replace target file
    try:
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on error
        tmp_path.unlink(missing_ok=True)
        raise


def store_baseline(
    baseline_dir: Path,
    edges: list[dict],
    graph_stats: dict | None = None,
) -> dict:
    """Store baseline edges and summary to disk.

    Creates baseline_edges.json and baseline_summary.json in the specified directory.

    Args:
        baseline_dir: Directory where baseline files will be stored.
        edges: List of edge dictionaries to store.

    Returns:
        Dictionary containing baseline_dir, baseline_hash_sha256, and edge_count.

    Raises:
        ValueError: If edges cannot be normalized (validation errors).
    """
    # Normalize edges
    normalized = normalize_edges(edges)

    # Compute hash
    hash_hex = compute_baseline_hash_sha256(normalized)

    # Write baseline_edges.json
    edges_payload = {"version": "1.0", "edges": normalized}
    edges_json = json.dumps(edges_payload, indent=2, ensure_ascii=True)
    edges_path = baseline_dir / "baseline_edges.json"
    atomic_write_text(edges_path, edges_json)

    # Write baseline_summary.json
    from datetime import datetime

    created_at = datetime.now(timezone.utc).isoformat()
    summary_payload = {
        "version": "1.0",
        "created_at_utc": created_at,
        "baseline_hash_sha256": hash_hex,
        "edge_count": len(normalized),
    }

    if graph_stats:
        included_files = graph_stats.get("included_files", 0)
        unmapped_files = graph_stats.get("unmapped_files", 0)
        unmapped_ratio = (
            float(unmapped_files) / included_files if included_files > 0 else 0.0
        )
        health = {
            "edge_count": len(normalized),
            "included_files": included_files,
            "unmapped_files": unmapped_files,
            "unmapped_ratio": unmapped_ratio,
            "unresolved_imports": graph_stats.get("unresolved_imports", 0),
        }
        buckets = graph_stats.get("unmapped_buckets")
        if isinstance(buckets, list):
            health["top_unmapped_buckets"] = buckets[:10]
        summary_payload["health"] = health
    summary_json = json.dumps(summary_payload, indent=2, ensure_ascii=True)
    summary_path = baseline_dir / "baseline_summary.json"
    atomic_write_text(summary_path, summary_json)

    return {
        "baseline_dir": str(baseline_dir),
        "baseline_hash_sha256": hash_hex,
        "edge_count": len(normalized),
    }


def load_baseline(baseline_dir: Path) -> dict:
    """Load and validate baseline files from disk.

    Reads baseline_edges.json and baseline_summary.json, validates their schema,
    and verifies hash integrity.

    Args:
        baseline_dir: Directory containing baseline files.

    Returns:
        Dictionary containing "edges" (normalized list) and "summary" (summary dict).

    Raises:
        ValueError: If files are missing, invalid JSON, schema invalid, or hash mismatch.
    """
    # Load baseline_edges.json
    edges_path = baseline_dir / "baseline_edges.json"
    if not edges_path.exists():
        raise ValueError(
            f"Missing baseline file 'baseline_edges.json' at expected path: {edges_path}"
        )

    try:
        with open(edges_path, "r", encoding="utf-8") as f:
            edges_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in 'baseline_edges.json': {e.msg} at line {e.lineno}, column {e.colno}"
        ) from e

    # Validate baseline_edges.json schema
    if not isinstance(edges_data, dict):
        raise ValueError("'baseline_edges.json': root must be an object")
    if "version" not in edges_data:
        raise ValueError("'baseline_edges.json': missing required key 'version'")
    if edges_data["version"] != "1.0":
        raise ValueError(
            f"'baseline_edges.json': unsupported version '{edges_data['version']}', expected '1.0'"
        )
    if "edges" not in edges_data:
        raise ValueError("'baseline_edges.json': missing required key 'edges'")
    if not isinstance(edges_data["edges"], list):
        raise ValueError(
            f"'baseline_edges.json': 'edges' must be a list, got {type(edges_data['edges']).__name__}"
        )

    # Load baseline_summary.json
    summary_path = baseline_dir / "baseline_summary.json"
    if not summary_path.exists():
        raise ValueError(
            f"Missing baseline file 'baseline_summary.json' at expected path: {summary_path}"
        )

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in 'baseline_summary.json': {e.msg} at line {e.lineno}, column {e.colno}"
        ) from e

    # Validate baseline_summary.json schema
    if not isinstance(summary_data, dict):
        raise ValueError("'baseline_summary.json': root must be an object")
    if "version" not in summary_data:
        raise ValueError("'baseline_summary.json': missing required key 'version'")
    if summary_data["version"] != "1.0":
        raise ValueError(
            f"'baseline_summary.json': unsupported version '{summary_data['version']}', expected '1.0'"
        )
    if "created_at_utc" not in summary_data:
        raise ValueError("'baseline_summary.json': missing required key 'created_at_utc'")
    if "baseline_hash_sha256" not in summary_data:
        raise ValueError("'baseline_summary.json': missing required key 'baseline_hash_sha256'")
    if "edge_count" not in summary_data:
        raise ValueError("'baseline_summary.json': missing required key 'edge_count'")

    # Validate hash format
    stored_hash = summary_data["baseline_hash_sha256"]
    if not isinstance(stored_hash, str):
        raise ValueError(
            f"'baseline_summary.json': 'baseline_hash_sha256' must be a string, got {type(stored_hash).__name__}"
        )
    if len(stored_hash) != 64:
        raise ValueError(
            f"'baseline_summary.json': 'baseline_hash_sha256' must be 64 characters, got {len(stored_hash)}"
        )

    # Validate edge_count
    stored_count = summary_data["edge_count"]
    if not isinstance(stored_count, int):
        raise ValueError(
            f"'baseline_summary.json': 'edge_count' must be an integer, got {type(stored_count).__name__}"
        )

    # Re-normalize edges and recompute hash
    normalized_edges = normalize_edges(edges_data["edges"])
    recomputed_hash = compute_baseline_hash_sha256(normalized_edges)

    # Verify hash matches
    if recomputed_hash != stored_hash:
        raise ValueError(
            f"Baseline hash mismatch: expected {stored_hash}, got {recomputed_hash}"
        )

    # Verify edge count matches
    if len(normalized_edges) != stored_count:
        raise ValueError(
            f"Edge count mismatch: expected {stored_count}, got {len(normalized_edges)}"
        )

    return {"edges": normalized_edges, "summary": summary_data}


def read_baseline_meta(baseline_dir: Path) -> dict | None:
    """Read baseline metadata from baseline_meta.json.

    Args:
        baseline_dir: Directory containing baseline files.

    Returns:
        Dictionary containing metadata (status, approved_by, approved_at, etc.) or None if file doesn't exist.
    """
    meta_path = baseline_dir / "baseline_meta.json"
    if not meta_path.exists():
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
    except json.JSONDecodeError:
        # Invalid JSON - treat as missing
        return None

    return meta_data


def write_baseline_meta(
    baseline_dir: Path,
    status: str,
    approved_by: str | None = None,
    approved_at: str | None = None,
    approval_note: str | None = None,
    baseline_hash: str | None = None,
) -> None:
    """Write baseline metadata to baseline_meta.json.

    Args:
        baseline_dir: Directory where baseline files are stored.
        status: Baseline status ("draft" or "accepted").
        approved_by: Name or email of approver (optional).
        approved_at: ISO 8601 UTC timestamp of approval (optional).
        approval_note: Optional approval note.
        baseline_hash: Baseline hash SHA-256 (optional).

    Raises:
        ValueError: If status is invalid.
    """
    if status not in ("draft", "accepted"):
        raise ValueError(f"Invalid status '{status}', must be 'draft' or 'accepted'")

    from datetime import datetime

    updated_at = datetime.now(timezone.utc).isoformat()

    meta_payload = {
        "version": "1.0",
        "status": status,
        "updated_at": updated_at,
    }

    if approved_by is not None:
        meta_payload["approved_by"] = approved_by
    if approved_at is not None:
        meta_payload["approved_at"] = approved_at
    if approval_note is not None:
        meta_payload["approval_note"] = approval_note
    if baseline_hash is not None:
        meta_payload["baseline_hash_sha256"] = baseline_hash

    meta_json = json.dumps(meta_payload, indent=2, ensure_ascii=True)
    meta_path = baseline_dir / "baseline_meta.json"
    atomic_write_text(meta_path, meta_json)


def read_baseline_exceptions(baseline_dir: Path) -> list[dict]:
    """Read baseline exceptions from baseline_exceptions.json.

    Args:
        baseline_dir: Directory containing baseline files.

    Returns:
        List of exception dictionaries, or empty list if file doesn't exist.
    """
    exceptions_path = baseline_dir / "baseline_exceptions.json"
    if not exceptions_path.exists():
        return []

    try:
        with open(exceptions_path, "r", encoding="utf-8") as f:
            exceptions_data = json.load(f)
    except json.JSONDecodeError:
        # Invalid JSON - treat as empty
        return []

    if not isinstance(exceptions_data, list):
        return []

    return exceptions_data


def write_baseline_exceptions(baseline_dir: Path, exceptions: list[dict]) -> None:
    """Write baseline exceptions to baseline_exceptions.json.

    Args:
        baseline_dir: Directory where baseline files are stored.
        exceptions: List of exception dictionaries.

    Raises:
        ValueError: If exception schema is invalid.
    """
    from datetime import datetime

    validated_exceptions = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for i, exc in enumerate(exceptions):
        if not isinstance(exc, dict):
            raise ValueError(f"Exception at index {i} must be a dictionary")

        # Validate required fields
        required_fields = ["from_module", "to_module", "owner", "reason", "expires_at"]
        for field in required_fields:
            if field not in exc:
                raise ValueError(f"Exception at index {i} missing required field '{field}'")
            if not isinstance(exc[field], str):
                raise ValueError(
                    f"Exception at index {i} '{field}' must be a string, got {type(exc[field]).__name__}"
                )
            if not exc[field]:
                raise ValueError(f"Exception at index {i} '{field}' must be non-empty")

        # Set created_at if missing
        if "created_at" not in exc:
            exc = exc.copy()
            exc["created_at"] = now_iso

        # Validate expires_at > created_at
        created_at = exc.get("created_at", now_iso)
        expires_at = exc["expires_at"]
        if expires_at <= created_at:
            raise ValueError(
                f"Exception at index {i} 'expires_at' ({expires_at}) must be after 'created_at' ({created_at})"
            )

        validated_exceptions.append(exc)

    exceptions_json = json.dumps(validated_exceptions, indent=2, ensure_ascii=True)
    exceptions_path = baseline_dir / "baseline_exceptions.json"
    atomic_write_text(exceptions_path, exceptions_json)


def get_active_exceptions(baseline_dir: Path, now: str | None = None) -> list[dict]:
    """Get active (non-expired) exceptions for a baseline.

    Args:
        baseline_dir: Directory containing baseline files.
        now: ISO 8601 UTC timestamp to use as "now" (optional).
            If None, uses current time.

    Returns:
        List of active exception dictionaries (expired ones filtered out).
    """
    from datetime import datetime

    if now is None:
        now = datetime.now(timezone.utc).isoformat()

    exceptions = read_baseline_exceptions(baseline_dir)
    active = []

    for exc in exceptions:
        expires_at = exc.get("expires_at")
        if expires_at is None:
            # No expiry - consider active
            active.append(exc)
        elif expires_at > now:
            # Not expired yet
            active.append(exc)
        # else: expired (expires_at <= now), skip

    return active

