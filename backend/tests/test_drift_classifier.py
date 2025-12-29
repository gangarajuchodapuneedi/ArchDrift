"""Tests for conformance-based drift classifier.

These tests verify that classify_drift() correctly classifies drift based on
conformance evidence (edges/rules/cycles) without using commit message keywords.
"""

import pytest

from utils.drift_classifier import classify_drift


def create_empty_analysis():
    """Create an empty analysis dict with all components."""
    return {
        "compare": {
            "edges_added": [],
            "edges_removed": [],
            "counts": {"divergence": 0, "absence": 0},
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 0, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }


def test_unknown_missing_rules():
    """Test that rules error produces unknown classification."""
    analysis = {
        "compare": {
            "edges_added": [],
            "edges_removed": [],
            "counts": {"divergence": 0, "absence": 0},
        },
        "rules": {
            "error": {"code": "missing_rules", "message": "Rules file not found"},
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "unknown"
    assert "missing_rules" in result["reason_codes"]


def test_unknown_missing_compare():
    """Test that missing compare produces unknown classification."""
    analysis = {
        "compare": None,
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 0, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "unknown"
    assert "missing_compare" in result["reason_codes"]


def test_unknown_missing_cycles():
    """Test that missing cycles produces unknown classification."""
    analysis = {
        "compare": {
            "edges_added": [],
            "edges_removed": [],
            "counts": {"divergence": 0, "absence": 0},
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 0, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": None,
    }

    result = classify_drift(analysis)

    assert result["classification"] == "unknown"
    assert "missing_cycles" in result["reason_codes"]


def test_no_change():
    """Test that all deltas zero produces no_change classification."""
    analysis = create_empty_analysis()

    result = classify_drift(analysis)

    assert result["classification"] == "no_change"
    assert result["reason_codes"] == []
    assert result["summary"]["edges_added_count"] == 0
    assert result["summary"]["edges_removed_count"] == 0
    assert result["summary"]["forbidden_edges_added_count"] == 0
    assert result["summary"]["cycles_added_count"] == 0


def test_negative_forbidden_edges_added():
    """Test that forbidden edges added produces negative classification."""
    analysis = {
        "compare": {
            "edges_added": [{"from": "api", "to": "db"}],
            "edges_removed": [],
            "counts": {"divergence": 1, "absence": 0},
        },
        "rules": {
            "forbidden_edges_added": [{"from": "api", "to": "db"}],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 1, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "negative"
    assert "forbidden_edges_added" in result["reason_codes"]
    assert result["summary"]["forbidden_edges_added_count"] == 1


def test_negative_cycles_added():
    """Test that cycles added produces negative classification."""
    analysis = {
        "compare": {
            "edges_added": [{"from": "A", "to": "B"}],
            "edges_removed": [],
            "counts": {"divergence": 1, "absence": 0},
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 0, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [["A", "B"]],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 1, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "negative"
    assert "cycles_added" in result["reason_codes"]
    assert result["summary"]["cycles_added_count"] == 1


def test_positive_forbidden_edges_removed():
    """Test that forbidden edges removed produces positive classification."""
    analysis = {
        "compare": {
            "edges_added": [],
            "edges_removed": [{"from": "api", "to": "db"}],
            "counts": {"divergence": 0, "absence": 1},
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [{"from": "api", "to": "db"}],
            "counts": {"forbidden_added": 0, "forbidden_removed": 1},
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "positive"
    assert "forbidden_edges_removed" in result["reason_codes"]
    assert result["summary"]["forbidden_edges_removed_count"] == 1


def test_positive_cycles_removed():
    """Test that cycles removed produces positive classification."""
    analysis = {
        "compare": {
            "edges_added": [],
            "edges_removed": [{"from": "A", "to": "B"}],
            "counts": {"divergence": 0, "absence": 1},
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 0, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [["A", "B"]],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 1},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "positive"
    assert "cycles_removed" in result["reason_codes"]
    assert result["summary"]["cycles_removed_count"] == 1


def test_needs_review():
    """Test that only allowed edges changed produces needs_review classification."""
    analysis = {
        "compare": {
            "edges_added": [{"from": "ui", "to": "core"}],
            "edges_removed": [],
            "counts": {"divergence": 1, "absence": 0},
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 0, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "needs_review"
    assert "allowed_edges_changed" in result["reason_codes"]
    assert result["summary"]["edges_added_count"] == 1
    assert result["summary"]["forbidden_edges_added_count"] == 0


def test_tie_break_negative_wins():
    """Test that negative wins when both forbidden edges added and removed."""
    analysis = {
        "compare": {
            "edges_added": [{"from": "api", "to": "db"}],
            "edges_removed": [{"from": "web", "to": "auth"}],
            "counts": {"divergence": 1, "absence": 1},
        },
        "rules": {
            "forbidden_edges_added": [{"from": "api", "to": "db"}],
            "forbidden_edges_removed": [{"from": "web", "to": "auth"}],
            "counts": {"forbidden_added": 1, "forbidden_removed": 1},
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    # Negative should win (risk-first)
    assert result["classification"] == "negative"
    assert "forbidden_edges_added" in result["reason_codes"]
    # Should not include forbidden_edges_removed in reason_codes (negative wins)


def test_tie_break_cycles_negative_wins():
    """Test that negative wins when both cycles added and removed."""
    analysis = {
        "compare": {
            "edges_added": [{"from": "A", "to": "B"}],
            "edges_removed": [{"from": "C", "to": "D"}],
            "counts": {"divergence": 1, "absence": 1},
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 0, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [["A", "B"]],
            "cycles_removed": [["C", "D"]],
            "counts": {"cycles_added_count": 1, "cycles_removed_count": 1},
        },
    }

    result = classify_drift(analysis)

    # Negative should win (risk-first)
    assert result["classification"] == "negative"
    assert "cycles_added" in result["reason_codes"]
    # Should not include cycles_removed in reason_codes (negative wins)


def test_reason_codes_sorted():
    """Test that reason_codes are sorted deterministically."""
    analysis = {
        "compare": {
            "edges_added": [{"from": "api", "to": "db"}],
            "edges_removed": [],
            "counts": {"divergence": 1, "absence": 0},
        },
        "rules": {
            "forbidden_edges_added": [{"from": "api", "to": "db"}],
            "forbidden_edges_removed": [],
            "counts": {"forbidden_added": 1, "forbidden_removed": 0},
            "error": None,
        },
        "cycles": {
            "cycles_added": [["A", "B"]],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 1, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "negative"
    # Reason codes should be sorted: "cycles_added" < "forbidden_edges_added"
    assert result["reason_codes"] == ["cycles_added", "forbidden_edges_added"]


def test_summary_counts_present():
    """Test that summary always includes all count fields."""
    analysis = create_empty_analysis()

    result = classify_drift(analysis)

    assert "summary" in result
    summary = result["summary"]
    assert "edges_added_count" in summary
    assert "edges_removed_count" in summary
    assert "forbidden_edges_added_count" in summary
    assert "forbidden_edges_removed_count" in summary
    assert "cycles_added_count" in summary
    assert "cycles_removed_count" in summary


def test_count_extraction_fallback():
    """Test that count extraction uses len() fallback when counts dict missing."""
    analysis = {
        "compare": {
            "edges_added": [{"from": "ui", "to": "core"}],
            "edges_removed": [],
            # Missing counts dict
        },
        "rules": {
            "forbidden_edges_added": [],
            "forbidden_edges_removed": [],
            # Missing counts dict
            "error": None,
        },
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            # Missing counts dict
        },
    }

    result = classify_drift(analysis)

    # Should use len() fallback
    assert result["summary"]["edges_added_count"] == 1
    assert result["summary"]["edges_removed_count"] == 0
    assert result["summary"]["forbidden_edges_added_count"] == 0
    assert result["summary"]["cycles_added_count"] == 0


def test_multiple_missing_components():
    """Test that multiple missing components combine reason_codes."""
    analysis = {
        "compare": None,
        "rules": None,
        "cycles": {
            "cycles_added": [],
            "cycles_removed": [],
            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
        },
    }

    result = classify_drift(analysis)

    assert result["classification"] == "unknown"
    assert "missing_compare" in result["reason_codes"]
    assert "missing_rules" in result["reason_codes"]
    assert len(result["reason_codes"]) == 2

