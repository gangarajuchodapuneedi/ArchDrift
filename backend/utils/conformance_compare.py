"""Conformance comparison utility for baseline vs current dependency graphs.

This module provides functions to compare baseline edges (expected architecture)
against current edges (observed architecture) and identify convergence, divergence,
and absence.
"""


def normalize_edge_input(edges: list[dict]) -> set[tuple[str, str]]:
    """Normalize a list of edge dictionaries to a set of tuples.

    Validates and converts edge dictionaries to tuples for efficient set operations.
    Handles duplicates automatically by using a set.

    Args:
        edges: List of edge dictionaries with "from" and "to" keys.

    Returns:
        Set of tuples (from_module, to_module).

    Raises:
        ValueError: If any edge is invalid (missing keys, empty strings, wrong types).
    """
    edge_set: set[tuple[str, str]] = set()

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

        edge_set.add((from_module, to_module))

    return edge_set


def compare_edges(baseline_edges: list[dict], current_edges: list[dict]) -> dict:
    """Compare baseline edges against current edges.

    Computes convergence (edges in both), divergence (edges added in current),
    and absence (edges removed from baseline).

    Args:
        baseline_edges: List of baseline edge dictionaries [{"from": str, "to": str}, ...].
        current_edges: List of current edge dictionaries [{"from": str, "to": str}, ...].

    Returns:
        Dictionary containing:
        - convergence: List of edge dicts present in both baseline and current (sorted)
        - divergence: List of edge dicts present in current but not in baseline (sorted)
        - absence: List of edge dicts present in baseline but not in current (sorted)
        - edges_added: Same as divergence (alias)
        - edges_removed: Same as absence (alias)
        - counts: Dictionary with baseline, current, convergence, divergence, absence counts

    Raises:
        ValueError: If edge format is invalid.
    """
    # Normalize inputs to sets of tuples
    baseline_set = normalize_edge_input(baseline_edges)
    current_set = normalize_edge_input(current_edges)

    # Compute set operations
    convergence_set = baseline_set & current_set  # Intersection
    divergence_set = current_set - baseline_set  # Current - Baseline (added)
    absence_set = baseline_set - current_set  # Baseline - Current (removed)

    # Convert sets back to sorted lists of dicts
    def set_to_sorted_dicts(edge_set: set[tuple[str, str]]) -> list[dict]:
        """Convert set of tuples to sorted list of edge dicts."""
        sorted_tuples = sorted(edge_set, key=lambda t: (t[0], t[1]))
        return [{"from": f, "to": t} for f, t in sorted_tuples]

    convergence = set_to_sorted_dicts(convergence_set)
    divergence = set_to_sorted_dicts(divergence_set)
    absence = set_to_sorted_dicts(absence_set)

    return {
        "convergence": convergence,
        "divergence": divergence,
        "absence": absence,
        "edges_added": divergence,  # Alias
        "edges_removed": absence,  # Alias
        "counts": {
            "baseline": len(baseline_set),
            "current": len(current_set),
            "convergence": len(convergence_set),
            "divergence": len(divergence_set),
            "absence": len(absence_set),
        },
    }

