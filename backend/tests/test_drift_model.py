"""Tests for Drift model conformance evidence fields."""

import pytest

from models.drift import Drift


def test_drift_without_new_fields_defaults():
    """Drift created without new fields should have safe defaults."""
    drift = Drift(
        id="d1",
        date="2024-01-01T00:00:00",
        type="negative",
        title="t",
        summary="s",
        functionality="f",
        files_changed=[],
        commit_hash="abc",
        repo_url="http://example.com",
    )

    assert drift.classification is None
    assert drift.edges_added_count == 0
    assert drift.edges_removed_count == 0
    assert drift.forbidden_edges_added_count == 0
    assert drift.forbidden_edges_removed_count == 0
    assert drift.cycles_added_count == 0
    assert drift.cycles_removed_count == 0
    assert drift.baseline_hash is None
    assert drift.rules_hash is None
    assert drift.reason_codes == []
    assert drift.evidence_preview == []


def test_drift_with_new_fields():
    """Drift created with new fields should preserve provided values."""
    drift = Drift(
        id="d2",
        date="2024-01-02T00:00:00",
        type="positive",
        title="t",
        summary="s",
        functionality="f",
        files_changed=[],
        commit_hash="def",
        repo_url="http://example.com",
        classification="positive",
        edges_added_count=3,
        edges_removed_count=1,
        forbidden_edges_added_count=2,
        forbidden_edges_removed_count=1,
        cycles_added_count=1,
        cycles_removed_count=0,
        baseline_hash="hash1",
        rules_hash="hash2",
        reason_codes=["cycles_added", "forbidden_edges_added"],
        evidence_preview=[{"edge": {"from": "a", "to": "b"}}],
    )

    assert drift.classification == "positive"
    assert drift.edges_added_count == 3
    assert drift.edges_removed_count == 1
    assert drift.forbidden_edges_added_count == 2
    assert drift.forbidden_edges_removed_count == 1
    assert drift.cycles_added_count == 1
    assert drift.cycles_removed_count == 0
    assert drift.baseline_hash == "hash1"
    assert drift.rules_hash == "hash2"
    assert drift.reason_codes == ["cycles_added", "forbidden_edges_added"]
    assert drift.evidence_preview == [{"edge": {"from": "a", "to": "b"}}]


def test_drift_from_dict_missing_new_fields():
    """Loading from dict without new fields should apply defaults."""
    payload = {
        "id": "d3",
        "date": "2024-01-03T00:00:00",
        "type": "negative",
        "title": "t",
        "summary": "s",
        "functionality": "f",
        "files_changed": [],
        "commit_hash": "ghi",
        "repo_url": "http://example.com",
    }

    drift = Drift(**payload)

    assert drift.classification is None
    assert drift.edges_added_count == 0
    assert drift.baseline_hash is None
    assert drift.reason_codes == []

