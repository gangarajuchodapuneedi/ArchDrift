"""Cycle detection utility for module dependency graphs.

This module provides functions to detect cycles in module dependency edges
and compare cycles between old and new edge sets.
"""

from utils.conformance_compare import normalize_edge_input

# Maximum number of cycles to detect before truncating
MAX_CYCLES = 200


def canonicalise_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Canonicalise a cycle to a stable representation.

    Rotates the cycle so the lexicographically smallest module is first,
    then chooses the lexicographically smaller of forward vs reversed.

    Args:
        cycle: List of module names forming a cycle (without repeating start).

    Returns:
        Canonical tuple representation of the cycle.
    """
    if not cycle:
        return tuple()

    if len(cycle) == 1:
        # Self-loop
        return (cycle[0],)

    # Find index of lexicographically smallest module in forward cycle
    min_idx = 0
    min_module = cycle[0]
    for i, module in enumerate(cycle):
        if module < min_module:
            min_module = module
            min_idx = i

    # Rotate forward so smallest is first
    forward_rotated = cycle[min_idx:] + cycle[:min_idx]

    # Reverse the cycle and find smallest in reversed
    reversed_cycle = list(reversed(cycle))
    rev_min_idx = 0
    rev_min_module = reversed_cycle[0]
    for i, module in enumerate(reversed_cycle):
        if module < rev_min_module:
            rev_min_module = module
            rev_min_idx = i

    # Rotate reversed so smallest is first
    reversed_rotated = reversed_cycle[rev_min_idx:] + reversed_cycle[:rev_min_idx]

    # Choose lexicographically smaller
    forward_tuple = tuple(forward_rotated)
    reversed_tuple = tuple(reversed_rotated)
    if reversed_tuple < forward_tuple:
        return reversed_tuple
    return forward_tuple


def detect_cycles(edges: list[dict], max_cycles: int = MAX_CYCLES) -> dict:
    """Detect cycles in a module dependency graph.

    Args:
        edges: List of edge dictionaries [{"from": str, "to": str}, ...].
        max_cycles: Maximum number of cycles to detect before truncating (default: 200).

    Returns:
        Dictionary containing:
        - cycles: List of cycle lists (each cycle is list of module names)
        - cycles_count: Number of cycles found
        - truncated: True if max_cycles was reached, False otherwise
    """
    # Normalize edges to set of tuples
    try:
        edge_set = normalize_edge_input(edges)
    except ValueError:
        # Invalid edges - return empty cycles
        return {
            "cycles": [],
            "cycles_count": 0,
            "truncated": False,
        }

    if not edge_set:
        return {
            "cycles": [],
            "cycles_count": 0,
            "truncated": False,
        }

    # Build adjacency list (sorted neighbors for deterministic traversal)
    adjacency: dict[str, list[str]] = {}
    for from_module, to_module in edge_set:
        if from_module not in adjacency:
            adjacency[from_module] = []
        adjacency[from_module].append(to_module)

    # Sort neighbors for deterministic traversal
    for node in adjacency:
        adjacency[node].sort()

    # Collect all nodes (including those that only appear as targets)
    all_nodes = set()
    for from_module, to_module in edge_set:
        all_nodes.add(from_module)
        all_nodes.add(to_module)

    # Detect cycles using DFS
    cycles_set: set[tuple[str, ...]] = set()
    truncated = False

    def dfs_cycles(node: str, path: list[str], visited_complete: set[str]):
        """DFS helper to detect cycles."""
        nonlocal truncated

        if truncated:
            return

        if node in path:
            # Cycle detected
            cycle_start_idx = path.index(node)
            # Extract cycle path without repeating start at end
            cycle_path = path[cycle_start_idx:]
            canonical = canonicalise_cycle(cycle_path)
            cycles_set.add(canonical)

            if len(cycles_set) >= max_cycles:
                truncated = True
            return

        if node in visited_complete:
            # Already explored this node completely
            return

        # Add to path
        path.append(node)

        # Visit neighbors
        if node in adjacency:
            for neighbor in adjacency[node]:
                dfs_cycles(neighbor, path, visited_complete)
                if truncated:
                    return

        # Remove from path
        path.pop()

        # Mark as completely visited
        visited_complete.add(node)

    # Iterate nodes in sorted order for deterministic results
    visited_complete: set[str] = set()
    for start_node in sorted(all_nodes):
        if start_node not in visited_complete:
            dfs_cycles(start_node, [], visited_complete)
            if truncated:
                break

    # Convert canonical tuples back to lists and sort
    cycles_list = [list(canonical) for canonical in sorted(cycles_set)]

    return {
        "cycles": cycles_list,
        "cycles_count": len(cycles_list),
        "truncated": truncated,
    }


def diff_cycles(
    old_edges: list[dict], new_edges: list[dict], max_cycles: int = MAX_CYCLES
) -> dict:
    """Compare cycles between old and new edge sets.

    Args:
        old_edges: List of old edge dictionaries [{"from": str, "to": str}, ...].
        new_edges: List of new edge dictionaries [{"from": str, "to": str}, ...].
        max_cycles: Maximum number of cycles to detect before truncating (default: 200).

    Returns:
        Dictionary containing:
        - old_cycles: List of cycles in old edges
        - new_cycles: List of cycles in new edges
        - cycles_added: List of cycles present in new but not in old
        - cycles_removed: List of cycles present in old but not in new
        - counts: Dictionary with old_cycles_count, new_cycles_count, cycles_added_count, cycles_removed_count
    """
    # Detect cycles in both sets
    old_result = detect_cycles(old_edges, max_cycles=max_cycles)
    new_result = detect_cycles(new_edges, max_cycles=max_cycles)

    old_cycles = old_result["cycles"]
    new_cycles = new_result["cycles"]

    # Convert to sets of canonical tuples for comparison
    old_cycles_set = {canonicalise_cycle(cycle) for cycle in old_cycles}
    new_cycles_set = {canonicalise_cycle(cycle) for cycle in new_cycles}

    # Compute differences
    cycles_added_set = new_cycles_set - old_cycles_set
    cycles_removed_set = old_cycles_set - new_cycles_set

    # Convert back to sorted lists
    cycles_added = [list(canonical) for canonical in sorted(cycles_added_set)]
    cycles_removed = [list(canonical) for canonical in sorted(cycles_removed_set)]

    return {
        "old_cycles": old_cycles,
        "new_cycles": new_cycles,
        "cycles_added": cycles_added,
        "cycles_removed": cycles_removed,
        "counts": {
            "old_cycles_count": len(old_cycles),
            "new_cycles_count": len(new_cycles),
            "cycles_added_count": len(cycles_added),
            "cycles_removed_count": len(cycles_removed),
        },
    }

