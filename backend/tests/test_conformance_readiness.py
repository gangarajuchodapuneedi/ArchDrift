import json
from pathlib import Path

import pytest

from services.drift_engine import commits_to_drifts
from utils.drift_classifier import assess_conformance_readiness


def test_assess_baseline_missing():
    ready, reasons = assess_conformance_readiness(
        baseline_summary=None,
        baseline_edges_count=None,
        graph_stats=None,
    )
    assert ready is False
    assert "BASELINE_MISSING" in reasons


def test_assess_baseline_empty():
    ready, reasons = assess_conformance_readiness(
        baseline_summary={"baseline_hash_sha256": "abc", "edge_count": 0},
        baseline_edges_count=0,
        graph_stats={"included_files": 10, "unmapped_files": 0},
    )
    assert ready is False
    assert "BASELINE_EMPTY" in reasons


def test_assess_mapping_too_low():
    ready, reasons = assess_conformance_readiness(
        baseline_summary={"baseline_hash_sha256": "abc", "edge_count": 1},
        baseline_edges_count=1,
        graph_stats={"included_files": 10, "unmapped_files": 6},
    )
    assert ready is False
    assert "MAPPING_TOO_LOW" in reasons


def test_assess_ready():
    ready, reasons = assess_conformance_readiness(
        baseline_summary={"baseline_hash_sha256": "abc", "edge_count": 2},
        baseline_edges_count=2,
        graph_stats={"included_files": 10, "unmapped_files": 2},
    )
    assert ready is True
    assert reasons == []


def test_commit_drift_baseline_missing_sets_unknown(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    # Minimal config and baseline placeholders
    config = object()
    baseline_data = {
        "baseline_hash": None,
        "baseline_summary": None,
        "baseline_edges_count": None,
        "active_exceptions": [],
    }
    drifts = commits_to_drifts(
        repo_url="repo",
        commits=[
            {"hash": "h1", "date": "2024-01-01T00:00:00Z", "message": "msg", "files_changed": []}
        ],
        max_drifts=1,
        repo_root_path=str(tmp_path),
        config=config,
        baseline_data=baseline_data,
        rules_hash=None,
    )
    assert len(drifts) == 1
    d = drifts[0]
    assert d.classification == "unknown"
    assert "BASELINE_MISSING" in d.reason_codes
    assert d.type != "positive" and d.type != "negative"


def test_commit_drift_ready_keeps_classification(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")

    class DummyConfig:
        modules = []
        unmapped_module_id = "unmapped"

    def fake_build_commit_delta(repo_path, commit_sha, config, limits):
        return {
            "edges_added": [{"from": "a", "to": "b"}],
            "edges_removed": [],
            "edges_added_count": 1,
            "edges_removed_count": 0,
            "evidence": [],
            "truncated": False,
            "stats": {"included_files": 10, "unmapped_files": 0},
        }

    def fake_check_rules(compare_like, config, active_exceptions):
        return {
            "counts": {
                "forbidden_added": 1,
                "forbidden_removed": 0,
            },
            "forbidden_edges_added": [{"from": "a", "to": "b"}],
            "forbidden_edges_removed": [],
            "error": None,
        }

    monkeypatch.setattr("services.drift_engine.build_commit_delta", fake_build_commit_delta)
    monkeypatch.setattr("services.drift_engine.check_rules", fake_check_rules)

    baseline_data = {
        "baseline_hash": "hash",
        "baseline_summary": {"baseline_hash_sha256": "hash", "edge_count": 1},
        "baseline_edges_count": 1,
        "active_exceptions": [],
    }

    drifts = commits_to_drifts(
        repo_url="repo",
        commits=[
            {"hash": "h1", "date": "2024-01-01T00:00:00Z", "message": "msg", "files_changed": []}
        ],
        max_drifts=1,
        repo_root_path=str(tmp_path),
        config=DummyConfig(),
        baseline_data=baseline_data,
        rules_hash="rh",
    )
    assert len(drifts) == 1
    d = drifts[0]
    assert d.classification != "unknown"
    assert "BASELINE_MISSING" not in d.reason_codes
    assert "keyword" not in (d.summary or "").lower()

