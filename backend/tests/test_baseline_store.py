"""Tests for baseline storage utility.

These tests verify that baseline_store functions correctly normalize edges,
compute stable hashes, store baseline files, and load/validate them with
tamper detection.
"""

import json
from pathlib import Path

import pytest

from utils.baseline_store import (
    compute_baseline_hash_sha256,
    load_baseline,
    normalize_edges,
    store_baseline,
)


def test_stable_hash_despite_order_and_duplicates():
    """Test that hash is stable despite input edge order and duplicates."""
    edges1 = [{"from": "b", "to": "a"}, {"from": "a", "to": "b"}, {"from": "a", "to": "b"}]
    edges2 = [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]

    normalized1 = normalize_edges(edges1)
    normalized2 = normalize_edges(edges2)

    # Both should normalize to same sorted list
    assert normalized1 == normalized2
    assert normalized1 == [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]

    # Hashes should be identical
    hash1 = compute_baseline_hash_sha256(normalized1)
    hash2 = compute_baseline_hash_sha256(normalized2)
    assert hash1 == hash2
    assert len(hash1) == 64
    assert len(hash2) == 64


def test_store_and_load_baseline(tmp_path):
    """Test that store_baseline writes both files and load_baseline reads them."""
    baseline_dir = tmp_path / "baseline"
    edges = [{"from": "ui", "to": "core"}, {"from": "core", "to": "api"}]

    result = store_baseline(baseline_dir, edges)

    assert result["edge_count"] == 2
    assert len(result["baseline_hash_sha256"]) == 64
    assert result["baseline_dir"] == str(baseline_dir)

    # Verify files exist
    edges_path = baseline_dir / "baseline_edges.json"
    summary_path = baseline_dir / "baseline_summary.json"
    assert edges_path.exists()
    assert summary_path.exists()

    # Load and verify
    loaded = load_baseline(baseline_dir)
    assert len(loaded["edges"]) == 2
    assert loaded["summary"]["edge_count"] == 2
    assert loaded["summary"]["baseline_hash_sha256"] == result["baseline_hash_sha256"]
    assert len(loaded["summary"]["baseline_hash_sha256"]) == 64


def test_hash_mismatch_detection(tmp_path):
    """Test that hash mismatch is detected when file is tampered with."""
    baseline_dir = tmp_path / "baseline"
    edges = [{"from": "ui", "to": "core"}]

    store_baseline(baseline_dir, edges)

    # Manually modify baseline_edges.json
    edges_path = baseline_dir / "baseline_edges.json"
    with open(edges_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["edges"].append({"from": "tampered", "to": "edge"})
    with open(edges_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Load should fail with hash mismatch
    with pytest.raises(ValueError) as exc_info:
        load_baseline(baseline_dir)
    assert "Baseline hash mismatch" in str(exc_info.value)


def test_missing_file_handling(tmp_path):
    """Test that missing files raise ValueError with clear message."""
    baseline_dir = tmp_path / "baseline"

    # Empty directory
    baseline_dir.mkdir()
    with pytest.raises(ValueError) as exc_info:
        load_baseline(baseline_dir)
    assert "baseline_edges.json" in str(exc_info.value)
    assert "Missing baseline file" in str(exc_info.value)

    # Only edges file exists
    edges_path = baseline_dir / "baseline_edges.json"
    edges_path.write_text('{"version":"1.0","edges":[]}')
    with pytest.raises(ValueError) as exc_info:
        load_baseline(baseline_dir)
    assert "baseline_summary.json" in str(exc_info.value)


def test_invalid_edge_schema(tmp_path):
    """Test that invalid edge schema raises ValueError."""
    baseline_dir = tmp_path / "baseline"

    # Empty "from"
    with pytest.raises(ValueError) as exc_info:
        store_baseline(baseline_dir, [{"from": "", "to": "x"}])
    assert "must be non-empty" in str(exc_info.value)

    # Empty "to"
    with pytest.raises(ValueError) as exc_info:
        store_baseline(baseline_dir, [{"from": "x", "to": ""}])
    assert "must be non-empty" in str(exc_info.value)

    # Missing "from"
    with pytest.raises(ValueError) as exc_info:
        store_baseline(baseline_dir, [{"to": "x"}])
    assert "missing required key 'from'" in str(exc_info.value)

    # Missing "to"
    with pytest.raises(ValueError) as exc_info:
        store_baseline(baseline_dir, [{"from": "x"}])
    assert "missing required key 'to'" in str(exc_info.value)


def test_deterministic_file_content(tmp_path):
    """Test that stored edges are sorted in baseline_edges.json."""
    baseline_dir = tmp_path / "baseline"
    edges = [
        {"from": "z", "to": "a"},
        {"from": "a", "to": "b"},
        {"from": "m", "to": "n"},
    ]

    store_baseline(baseline_dir, edges)

    # Read and verify edges are sorted
    edges_path = baseline_dir / "baseline_edges.json"
    with open(edges_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stored_edges = data["edges"]
    assert stored_edges == [
        {"from": "a", "to": "b"},
        {"from": "m", "to": "n"},
        {"from": "z", "to": "a"},
    ]


def test_empty_edges_list(tmp_path):
    """Test that empty edges list works correctly."""
    baseline_dir = tmp_path / "baseline"
    edges = []

    result = store_baseline(baseline_dir, edges)
    assert result["edge_count"] == 0

    loaded = load_baseline(baseline_dir)
    assert len(loaded["edges"]) == 0
    assert loaded["summary"]["edge_count"] == 0


def test_single_edge(tmp_path):
    """Test that single edge works correctly."""
    baseline_dir = tmp_path / "baseline"
    edges = [{"from": "moduleA", "to": "moduleB"}]

    result = store_baseline(baseline_dir, edges)
    assert result["edge_count"] == 1

    loaded = load_baseline(baseline_dir)
    assert len(loaded["edges"]) == 1
    assert loaded["edges"][0] == {"from": "moduleA", "to": "moduleB"}


def test_multiple_edges(tmp_path):
    """Test that multiple edges are handled correctly."""
    baseline_dir = tmp_path / "baseline"
    edges = [
        {"from": "ui", "to": "core"},
        {"from": "core", "to": "api"},
        {"from": "api", "to": "db"},
    ]

    result = store_baseline(baseline_dir, edges)
    assert result["edge_count"] == 3

    loaded = load_baseline(baseline_dir)
    assert len(loaded["edges"]) == 3
    # Verify sorted order
    assert loaded["edges"][0]["from"] == "api"
    assert loaded["edges"][1]["from"] == "core"
    assert loaded["edges"][2]["from"] == "ui"


def test_edge_count_validation(tmp_path):
    """Test that edge count is validated correctly."""
    baseline_dir = tmp_path / "baseline"
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]

    store_baseline(baseline_dir, edges)

    # Manually modify edge_count in summary
    summary_path = baseline_dir / "baseline_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["edge_count"] = 999
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Load should fail with edge count mismatch
    with pytest.raises(ValueError) as exc_info:
        load_baseline(baseline_dir)
    assert "Edge count mismatch" in str(exc_info.value)


def test_timestamp_format(tmp_path):
    """Test that timestamp is in ISO 8601 format."""
    baseline_dir = tmp_path / "baseline"
    edges = [{"from": "a", "to": "b"}]

    store_baseline(baseline_dir, edges)

    loaded = load_baseline(baseline_dir)
    created_at = loaded["summary"]["created_at_utc"]
    assert isinstance(created_at, str)
    # Should contain 'T' separator and timezone indicator
    assert "T" in created_at
    assert "+00:00" in created_at or "Z" in created_at


def test_invalid_json_handling(tmp_path):
    """Test that invalid JSON raises ValueError with clear message."""
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()

    # Write invalid JSON
    edges_path = baseline_dir / "baseline_edges.json"
    edges_path.write_text("{ invalid json }")

    with pytest.raises(ValueError) as exc_info:
        load_baseline(baseline_dir)
    assert "Invalid JSON" in str(exc_info.value)
    assert "baseline_edges.json" in str(exc_info.value)


def test_version_validation(tmp_path):
    """Test that version validation works correctly."""
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()

    # Write edges file with wrong version
    edges_path = baseline_dir / "baseline_edges.json"
    edges_path.write_text('{"version":"2.0","edges":[]}')

    summary_path = baseline_dir / "baseline_summary.json"
    summary_path.write_text(
        '{"version":"1.0","created_at_utc":"2024-01-01T00:00:00+00:00","baseline_hash_sha256":"' + "0" * 64 + '","edge_count":0}'
    )

    with pytest.raises(ValueError) as exc_info:
        load_baseline(baseline_dir)
    assert "unsupported version" in str(exc_info.value) or "version" in str(exc_info.value).lower()


def test_hash_length_validation(tmp_path):
    """Test that hash length is validated."""
    baseline_dir = tmp_path / "baseline"
    edges = [{"from": "a", "to": "b"}]

    store_baseline(baseline_dir, edges)

    # Manually modify hash to wrong length
    summary_path = baseline_dir / "baseline_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["baseline_hash_sha256"] = "short"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    with pytest.raises(ValueError) as exc_info:
        load_baseline(baseline_dir)
    assert "64 characters" in str(exc_info.value)

