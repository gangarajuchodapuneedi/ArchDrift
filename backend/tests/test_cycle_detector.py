"""Tests for cycle detection utility.

These tests verify that detect_cycles() correctly identifies cycles in
module dependency graphs and that diff_cycles() correctly compares cycles.
"""

import pytest

from utils.cycle_detector import canonicalise_cycle, detect_cycles, diff_cycles


def test_no_edges_no_cycles():
    """Test that empty edges produce no cycles."""
    edges = []

    result = detect_cycles(edges)

    assert result["cycles"] == []
    assert result["cycles_count"] == 0
    assert result["truncated"] is False


def test_self_loop():
    """Test that self-loop A->A produces cycle [A]."""
    edges = [{"from": "A", "to": "A"}]

    result = detect_cycles(edges)

    assert result["cycles_count"] == 1
    assert ["A"] in result["cycles"]
    assert result["truncated"] is False


def test_simple_2_cycle():
    """Test that A->B, B->A produces one canonical cycle."""
    edges = [
        {"from": "A", "to": "B"},
        {"from": "B", "to": "A"},
    ]

    result = detect_cycles(edges)

    assert result["cycles_count"] == 1
    # Cycle should be canonicalised (A, B) or (B, A) - lexicographically smaller first
    assert len(result["cycles"]) == 1
    cycle = result["cycles"][0]
    assert set(cycle) == {"A", "B"}
    assert len(cycle) == 2
    assert result["truncated"] is False


def test_3_cycle():
    """Test that A->B, B->C, C->A produces one canonical cycle."""
    edges = [
        {"from": "A", "to": "B"},
        {"from": "B", "to": "C"},
        {"from": "C", "to": "A"},
    ]

    result = detect_cycles(edges)

    assert result["cycles_count"] == 1
    assert len(result["cycles"]) == 1
    cycle = result["cycles"][0]
    assert set(cycle) == {"A", "B", "C"}
    assert len(cycle) == 3
    # Should be canonicalised (A first, as lexicographically smallest)
    assert cycle[0] == "A"
    assert result["truncated"] is False


def test_multiple_cycles():
    """Test that graph with two distinct cycles returns both."""
    edges = [
        # Cycle 1: A->B->A
        {"from": "A", "to": "B"},
        {"from": "B", "to": "A"},
        # Cycle 2: C->D->E->C
        {"from": "C", "to": "D"},
        {"from": "D", "to": "E"},
        {"from": "E", "to": "C"},
    ]

    result = detect_cycles(edges)

    assert result["cycles_count"] == 2
    assert len(result["cycles"]) == 2
    # Both cycles should be present
    cycle_sets = [set(cycle) for cycle in result["cycles"]]
    assert {"A", "B"} in cycle_sets
    assert {"C", "D", "E"} in cycle_sets
    assert result["truncated"] is False


def test_duplicate_rotation_reversal_dedupe():
    """Test that same cycle is not returned multiple times."""
    # Same cycle represented in different ways
    edges = [
        {"from": "A", "to": "B"},
        {"from": "B", "to": "C"},
        {"from": "C", "to": "A"},
        # Duplicate edges (should be deduplicated by normalize_edge_input)
        {"from": "A", "to": "B"},
        {"from": "B", "to": "C"},
        {"from": "C", "to": "A"},
    ]

    result = detect_cycles(edges)

    # Should only find one cycle despite duplicates
    assert result["cycles_count"] == 1
    assert len(result["cycles"]) == 1
    assert result["truncated"] is False


def test_deterministic_ordering():
    """Test that shuffled input produces same output."""
    edges1 = [
        {"from": "Z", "to": "A"},
        {"from": "A", "to": "B"},
        {"from": "B", "to": "C"},
        {"from": "C", "to": "Z"},
    ]
    edges2 = [
        {"from": "B", "to": "C"},
        {"from": "C", "to": "Z"},
        {"from": "Z", "to": "A"},
        {"from": "A", "to": "B"},
    ]

    result1 = detect_cycles(edges1)
    result2 = detect_cycles(edges2)

    # Results should be identical (canonicalised and sorted)
    assert result1["cycles"] == result2["cycles"]
    assert result1["cycles_count"] == result2["cycles_count"]


def test_diff_cycles_added():
    """Test that new graph introducing cycle reports it in cycles_added."""
    old_edges = [
        {"from": "A", "to": "B"},
    ]
    new_edges = [
        {"from": "A", "to": "B"},
        {"from": "B", "to": "A"},  # Creates cycle
    ]

    result = diff_cycles(old_edges, new_edges)

    assert result["counts"]["old_cycles_count"] == 0
    assert result["counts"]["new_cycles_count"] == 1
    assert result["counts"]["cycles_added_count"] == 1
    assert result["counts"]["cycles_removed_count"] == 0
    assert len(result["cycles_added"]) == 1
    assert len(result["cycles_removed"]) == 0


def test_diff_cycles_removed():
    """Test that new graph removing cycle reports it in cycles_removed."""
    old_edges = [
        {"from": "A", "to": "B"},
        {"from": "B", "to": "A"},  # Cycle exists
    ]
    new_edges = [
        {"from": "A", "to": "B"},  # Cycle broken
    ]

    result = diff_cycles(old_edges, new_edges)

    assert result["counts"]["old_cycles_count"] == 1
    assert result["counts"]["new_cycles_count"] == 0
    assert result["counts"]["cycles_added_count"] == 0
    assert result["counts"]["cycles_removed_count"] == 1
    assert len(result["cycles_added"]) == 0
    assert len(result["cycles_removed"]) == 1


def test_max_cycles_cap():
    """Test that max_cycles cap is enforced."""
    # Create a graph with many cycles (complete graph of 10 nodes has many cycles)
    # For simplicity, create multiple independent 2-cycles
    edges = []
    for i in range(150):  # Create 150 independent 2-cycles
        node_a = f"A{i}"
        node_b = f"B{i}"
        edges.append({"from": node_a, "to": node_b})
        edges.append({"from": node_b, "to": node_a})

    result = detect_cycles(edges, max_cycles=100)

    # Should hit the cap
    assert result["truncated"] is True
    assert result["cycles_count"] == 100
    assert len(result["cycles"]) == 100


def test_canonicalise_cycle():
    """Test canonicalise_cycle helper function."""
    # Test rotation to smallest
    cycle1 = ["B", "C", "A"]
    canonical1 = canonicalise_cycle(cycle1)
    assert canonical1[0] == "A"  # Smallest should be first

    # Test self-loop
    cycle2 = ["A"]
    canonical2 = canonicalise_cycle(cycle2)
    assert canonical2 == ("A",)

    # Test forward vs reversed choice
    cycle3 = ["A", "B"]
    canonical3 = canonicalise_cycle(cycle3)
    # Should choose lexicographically smaller: (A, B) vs (B, A) -> (A, B)
    assert canonical3 == ("A", "B")


def test_invalid_edges():
    """Test that invalid edges are handled gracefully."""
    invalid_edges = [
        {"from": "A"},  # Missing "to"
    ]

    result = detect_cycles(invalid_edges)

    # Should return empty cycles (normalize_edge_input raises ValueError)
    assert result["cycles"] == []
    assert result["cycles_count"] == 0
    assert result["truncated"] is False


def test_complex_graph_multiple_paths():
    """Test cycle detection in a more complex graph."""
    edges = [
        # Cycle 1: A->B->C->A
        {"from": "A", "to": "B"},
        {"from": "B", "to": "C"},
        {"from": "C", "to": "A"},
        # Cycle 2: D->E->D
        {"from": "D", "to": "E"},
        {"from": "E", "to": "D"},
        # Additional edges that don't create cycles
        {"from": "A", "to": "D"},
        {"from": "D", "to": "F"},
    ]

    result = detect_cycles(edges)

    assert result["cycles_count"] == 2
    cycle_sets = [set(cycle) for cycle in result["cycles"]]
    assert {"A", "B", "C"} in cycle_sets
    assert {"D", "E"} in cycle_sets

