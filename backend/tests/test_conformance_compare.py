"""Tests for conformance comparison utility.

These tests verify that compare_edges() correctly identifies convergence,
divergence, and absence between baseline and current edges.
"""

import pytest

from utils.conformance_compare import compare_edges, normalize_edge_input


def test_exact_match():
    """Test that exact match produces no divergence or absence."""
    baseline = [{"from": "ui", "to": "core"}, {"from": "api", "to": "db"}]
    current = [{"from": "ui", "to": "core"}, {"from": "api", "to": "db"}]

    result = compare_edges(baseline, current)

    # Convergence should be sorted (alphabetically by "from", then "to")
    expected_convergence = [{"from": "api", "to": "db"}, {"from": "ui", "to": "core"}]
    assert result["convergence"] == expected_convergence
    assert result["divergence"] == []
    assert result["absence"] == []
    assert result["edges_added"] == []
    assert result["edges_removed"] == []
    assert result["counts"]["baseline"] == 2
    assert result["counts"]["current"] == 2
    assert result["counts"]["convergence"] == 2
    assert result["counts"]["divergence"] == 0
    assert result["counts"]["absence"] == 0


def test_added_edge():
    """Test that added edge appears in divergence and edges_added."""
    baseline = [{"from": "ui", "to": "core"}]
    current = [{"from": "ui", "to": "core"}, {"from": "api", "to": "db"}]

    result = compare_edges(baseline, current)

    assert result["convergence"] == [{"from": "ui", "to": "core"}]
    assert result["divergence"] == [{"from": "api", "to": "db"}]
    assert result["absence"] == []
    assert result["edges_added"] == [{"from": "api", "to": "db"}]
    assert result["edges_removed"] == []
    assert result["counts"]["baseline"] == 1
    assert result["counts"]["current"] == 2
    assert result["counts"]["convergence"] == 1
    assert result["counts"]["divergence"] == 1
    assert result["counts"]["absence"] == 0


def test_removed_edge():
    """Test that removed edge appears in absence and edges_removed."""
    baseline = [{"from": "ui", "to": "core"}, {"from": "api", "to": "db"}]
    current = [{"from": "ui", "to": "core"}]

    result = compare_edges(baseline, current)

    assert result["convergence"] == [{"from": "ui", "to": "core"}]
    assert result["divergence"] == []
    assert result["absence"] == [{"from": "api", "to": "db"}]
    assert result["edges_added"] == []
    assert result["edges_removed"] == [{"from": "api", "to": "db"}]
    assert result["counts"]["baseline"] == 2
    assert result["counts"]["current"] == 1
    assert result["counts"]["convergence"] == 1
    assert result["counts"]["divergence"] == 0
    assert result["counts"]["absence"] == 1


def test_mixed_changes():
    """Test that mixed changes (both add and remove) are correctly identified."""
    baseline = [{"from": "ui", "to": "core"}, {"from": "api", "to": "db"}]
    current = [{"from": "ui", "to": "core"}, {"from": "web", "to": "auth"}]

    result = compare_edges(baseline, current)

    assert result["convergence"] == [{"from": "ui", "to": "core"}]
    assert result["divergence"] == [{"from": "web", "to": "auth"}]
    assert result["absence"] == [{"from": "api", "to": "db"}]
    assert result["edges_added"] == [{"from": "web", "to": "auth"}]
    assert result["edges_removed"] == [{"from": "api", "to": "db"}]
    assert result["counts"]["baseline"] == 2
    assert result["counts"]["current"] == 2
    assert result["counts"]["convergence"] == 1
    assert result["counts"]["divergence"] == 1
    assert result["counts"]["absence"] == 1


def test_deterministic_ordering():
    """Test that output order is deterministic regardless of input order."""
    baseline = [{"from": "z", "to": "a"}, {"from": "a", "to": "b"}, {"from": "m", "to": "n"}]
    current = [{"from": "m", "to": "n"}, {"from": "z", "to": "a"}, {"from": "a", "to": "b"}]

    result1 = compare_edges(baseline, current)

    # Shuffle input order
    baseline_shuffled = [{"from": "m", "to": "n"}, {"from": "z", "to": "a"}, {"from": "a", "to": "b"}]
    current_shuffled = [{"from": "a", "to": "b"}, {"from": "m", "to": "n"}, {"from": "z", "to": "a"}]

    result2 = compare_edges(baseline_shuffled, current_shuffled)

    # Results should be identical (sorted)
    assert result1["convergence"] == result2["convergence"]
    assert result1["convergence"] == [
        {"from": "a", "to": "b"},
        {"from": "m", "to": "n"},
        {"from": "z", "to": "a"},
    ]


def test_duplicate_handling():
    """Test that duplicate edges in input do not affect counts or output."""
    baseline = [
        {"from": "ui", "to": "core"},
        {"from": "ui", "to": "core"},  # Duplicate
        {"from": "api", "to": "db"},
    ]
    current = [
        {"from": "ui", "to": "core"},
        {"from": "api", "to": "db"},
        {"from": "api", "to": "db"},  # Duplicate
        {"from": "web", "to": "auth"},
    ]

    result = compare_edges(baseline, current)

    # Duplicates should be deduplicated
    assert result["counts"]["baseline"] == 2  # Not 3
    assert result["counts"]["current"] == 3  # Not 4
    assert result["counts"]["convergence"] == 2
    assert result["counts"]["divergence"] == 1
    assert result["counts"]["absence"] == 0

    # Output should not contain duplicates
    assert len(result["convergence"]) == 2
    assert len(result["divergence"]) == 1
    assert len(result["absence"]) == 0

    # Verify content
    assert {"from": "ui", "to": "core"} in result["convergence"]
    assert {"from": "api", "to": "db"} in result["convergence"]
    assert result["divergence"] == [{"from": "web", "to": "auth"}]


def test_empty_inputs():
    """Test that empty baseline or current produces appropriate results."""
    baseline = [{"from": "ui", "to": "core"}]
    current_empty = []

    result1 = compare_edges(baseline, current_empty)

    assert result1["convergence"] == []
    assert result1["divergence"] == []
    assert result1["absence"] == [{"from": "ui", "to": "core"}]
    assert result1["counts"]["baseline"] == 1
    assert result1["counts"]["current"] == 0
    assert result1["counts"]["convergence"] == 0
    assert result1["counts"]["divergence"] == 0
    assert result1["counts"]["absence"] == 1

    baseline_empty = []
    current = [{"from": "ui", "to": "core"}]

    result2 = compare_edges(baseline_empty, current)

    assert result2["convergence"] == []
    assert result2["divergence"] == [{"from": "ui", "to": "core"}]
    assert result2["absence"] == []
    assert result2["counts"]["baseline"] == 0
    assert result2["counts"]["current"] == 1
    assert result2["counts"]["convergence"] == 0
    assert result2["counts"]["divergence"] == 1
    assert result2["counts"]["absence"] == 0


def test_both_empty():
    """Test that both empty inputs produce all empty results."""
    baseline = []
    current = []

    result = compare_edges(baseline, current)

    assert result["convergence"] == []
    assert result["divergence"] == []
    assert result["absence"] == []
    assert result["edges_added"] == []
    assert result["edges_removed"] == []
    assert result["counts"]["baseline"] == 0
    assert result["counts"]["current"] == 0
    assert result["counts"]["convergence"] == 0
    assert result["counts"]["divergence"] == 0
    assert result["counts"]["absence"] == 0


def test_normalize_edge_input_validation():
    """Test that normalize_edge_input validates edge format."""
    # Valid input
    valid_edges = [{"from": "ui", "to": "core"}]
    result = normalize_edge_input(valid_edges)
    assert result == {("ui", "core")}

    # Missing "from" key
    with pytest.raises(ValueError) as exc_info:
        normalize_edge_input([{"to": "core"}])
    assert "missing required key 'from'" in str(exc_info.value)

    # Missing "to" key
    with pytest.raises(ValueError) as exc_info:
        normalize_edge_input([{"from": "ui"}])
    assert "missing required key 'to'" in str(exc_info.value)

    # Empty "from" string
    with pytest.raises(ValueError) as exc_info:
        normalize_edge_input([{"from": "", "to": "core"}])
    assert "must be non-empty" in str(exc_info.value)

    # Empty "to" string
    with pytest.raises(ValueError) as exc_info:
        normalize_edge_input([{"from": "ui", "to": ""}])
    assert "must be non-empty" in str(exc_info.value)

    # Non-dict input
    with pytest.raises(ValueError) as exc_info:
        normalize_edge_input(["not a dict"])
    assert "must be a dictionary" in str(exc_info.value)

    # Non-string "from"
    with pytest.raises(ValueError) as exc_info:
        normalize_edge_input([{"from": 123, "to": "core"}])
    assert "must be a string" in str(exc_info.value)

    # Non-string "to"
    with pytest.raises(ValueError) as exc_info:
        normalize_edge_input([{"from": "ui", "to": 456}])
    assert "must be a string" in str(exc_info.value)


def test_compare_edges_sorted_output():
    """Test that output edges are sorted lexicographically."""
    baseline = [
        {"from": "zebra", "to": "alpha"},
        {"from": "alpha", "to": "beta"},
        {"from": "middle", "to": "node"},
    ]
    current = [
        {"from": "zebra", "to": "alpha"},
        {"from": "alpha", "to": "beta"},
        {"from": "middle", "to": "node"},
        {"from": "new", "to": "old"},
    ]

    result = compare_edges(baseline, current)

    # Verify convergence is sorted
    assert result["convergence"] == [
        {"from": "alpha", "to": "beta"},
        {"from": "middle", "to": "node"},
        {"from": "zebra", "to": "alpha"},
    ]

    # Verify divergence is sorted
    assert result["divergence"] == [{"from": "new", "to": "old"}]

