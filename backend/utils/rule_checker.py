"""Rule checker for validating dependency graph edges against allowed rules and exceptions.

This module provides functions to check if edges_added and edges_removed from a
conformance compare result violate the allowed rules defined in allowed_rules.json
and whether any violations are allowed via active baseline exceptions.
"""

from utils.architecture_config import ArchitectureConfig
from utils.conformance_compare import normalize_edge_input


def build_allowed_set_from_rules(config: ArchitectureConfig) -> set[tuple[str, str]]:
    """Build a set of allowed edges from architecture configuration.

    Args:
        config: ArchitectureConfig object containing allowed_edges.

    Returns:
        Set of tuples (from_module, to_module) representing allowed edges.
    """
    allowed_set: set[tuple[str, str]] = set()

    for allowed_edge in config.allowed_edges:
        allowed_set.add((allowed_edge.from_module, allowed_edge.to_module))

    return allowed_set


def build_exception_set_and_map(
    active_exceptions: list[dict],
) -> tuple[set[tuple[str, str]], dict[tuple[str, str], dict]]:
    """Build exception set and map from active exceptions.

    Filters out expired exceptions based on expires_at timestamp.

    Args:
        active_exceptions: List of exception dictionaries (may include expired).

    Returns:
        Tuple of (exception_set, exception_map) where:
        - exception_set: Set of tuples (from_module, to_module) for active exceptions only
        - exception_map: Dict mapping edge tuple to exception dict for active exceptions only
    """
    from datetime import datetime, timezone

    exception_set: set[tuple[str, str]] = set()
    exception_map: dict[tuple[str, str], dict] = {}

    now = datetime.now(timezone.utc).isoformat()

    for exc in active_exceptions:
        from_module = exc.get("from_module")
        to_module = exc.get("to_module")

        # Skip invalid exceptions (missing required fields)
        if not from_module or not to_module:
            continue

        # Check if exception is expired
        expires_at = exc.get("expires_at")
        if expires_at is not None and expires_at <= now:
            # Expired - skip
            continue

        edge_tuple = (from_module, to_module)
        exception_set.add(edge_tuple)
        exception_map[edge_tuple] = exc

    return exception_set, exception_map


def check_rules(
    compare_result: dict,
    config: ArchitectureConfig,
    active_exceptions: list[dict],
) -> dict:
    """Check compare result against allowed rules and active exceptions.

    Args:
        compare_result: Dictionary from compare_edges() containing:
            - edges_added: List of edge dicts [{"from": str, "to": str}, ...]
            - edges_removed: List of edge dicts [{"from": str, "to": str}, ...]
        config: ArchitectureConfig object with allowed_edges.
        active_exceptions: List of active exception dictionaries.

    Returns:
        Dictionary containing:
        - ok: bool (False if any violations)
        - forbidden_edges_added: List of forbidden edge dicts (sorted)
        - forbidden_edges_removed: List (always empty, no required edges concept)
        - allowed_via_exception: List of exception-allowed edge dicts (sorted)
        - violations: List of violation dicts
        - counts: Dictionary with various counts
        - error: None or error dict
    """
    # Normalize edges_added and edges_removed to sets of tuples
    edges_added = compare_result.get("edges_added", [])
    edges_removed = compare_result.get("edges_removed", [])

    try:
        edges_added_set = normalize_edge_input(edges_added)
    except ValueError as e:
        return {
            "ok": False,
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "allowed_via_exception": [],
            "violations": [],
            "counts": {
                "edges_added": 0,
                "edges_removed": 0,
                "forbidden_added": 0,
                "forbidden_removed": 0,
                "exception_allowed": 0,
            },
            "error": {
                "code": "invalid_edges_added",
                "message": str(e),
                "details": {},
            },
        }

    try:
        edges_removed_set = normalize_edge_input(edges_removed)
    except ValueError as e:
        return {
            "ok": False,
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "allowed_via_exception": [],
            "violations": [],
            "counts": {
                "edges_added": 0,
                "edges_removed": 0,
                "forbidden_added": 0,
                "forbidden_removed": 0,
                "exception_allowed": 0,
            },
            "error": {
                "code": "invalid_edges_removed",
                "message": str(e),
                "details": {},
            },
        }

    # Build allowed set from config
    allowed_set = build_allowed_set_from_rules(config)

    # Build exception set and map
    exception_set, exception_map = build_exception_set_and_map(active_exceptions)

    # Compute forbidden edges (added)
    # If deny_by_default=False and allowed_edges is empty, allow all edges (forbidden_added_set = empty)
    # Otherwise, edges not in allowed_set are forbidden
    if not config.deny_by_default and len(allowed_set) == 0:
        # Allow all edges when deny_by_default=False and allowed_edges is empty
        forbidden_added_set: set[tuple[str, str]] = set()
    else:
        # Standard behavior: edges not in allowed_set are forbidden
        forbidden_added_set = edges_added_set - allowed_set

    # Check which forbidden edges are allowed via exception
    exception_allowed_set = forbidden_added_set & exception_set
    forbidden_added_final_set = forbidden_added_set - exception_allowed_set

    # Forbidden removed (always empty - no required edges concept)
    forbidden_removed_set: set[tuple[str, str]] = set()

    # Convert sets back to sorted lists of dicts
    def set_to_sorted_dicts(edge_set: set[tuple[str, str]]) -> list[dict]:
        """Convert set of tuples to sorted list of edge dicts."""
        sorted_tuples = sorted(edge_set, key=lambda t: (t[0], t[1]))
        return [{"from": f, "to": t} for f, t in sorted_tuples]

    forbidden_edges_added = set_to_sorted_dicts(forbidden_added_final_set)
    forbidden_edges_removed = set_to_sorted_dicts(forbidden_removed_set)
    allowed_via_exception = set_to_sorted_dicts(exception_allowed_set)

    # Build violations list
    violations = []
    for edge_tuple in sorted(forbidden_added_final_set, key=lambda t: (t[0], t[1])):
        violations.append(
            {
                "type": "forbidden_added",
                "edge": {"from": edge_tuple[0], "to": edge_tuple[1]},
                "rule_id": None,  # No rule IDs in current format
                "reason": "Edge not in allowed_rules.json",
                "exception": None,
            }
        )

    # Determine ok status
    ok = len(forbidden_added_final_set) == 0 and len(forbidden_removed_set) == 0

    return {
        "ok": ok,
        "forbidden_edges_added": forbidden_edges_added,
        "forbidden_edges_removed": forbidden_edges_removed,
        "allowed_via_exception": allowed_via_exception,
        "violations": violations,
        "counts": {
            "edges_added": len(edges_added_set),
            "edges_removed": len(edges_removed_set),
            "forbidden_added": len(forbidden_added_final_set),
            "forbidden_removed": len(forbidden_removed_set),
            "exception_allowed": len(exception_allowed_set),
        },
        "error": None,
    }

