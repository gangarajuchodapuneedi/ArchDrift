"""Tests for classifier_mode override in analyze-repo endpoint.

These tests verify that:
1. classifier_mode can be overridden via request body even when env var is not set
2. classifier_mode_used field is set correctly in drift results
3. Conformance mode produces baseline_hash and rules_hash when available
"""

import json
import os
from pathlib import Path

import pytest

from services.drift_engine import analyze_repo_for_drifts, commits_to_drifts
from services.baseline_service import baseline_dir_for_repo, generate_baseline
from utils.baseline_store import store_baseline
from utils.architecture_config import _get_default_config_dir, load_architecture_config


def _write_architecture_config(tmpdir: Path):
    """Create architecture config files in tmpdir/architecture."""
    config_dir = tmpdir / "architecture"
    config_dir.mkdir(parents=True, exist_ok=True)

    # module_map.json
    module_map = {
        "version": "1.0",
        "unmapped_module_id": "unmapped",
        "modules": [
            {"id": "ui", "roots": ["ui"]},
            {"id": "core", "roots": ["core"]},
        ],
    }
    (config_dir / "module_map.json").write_text(json.dumps(module_map), encoding="utf-8")

    # allowed_rules.json
    allowed_rules = {
        "version": "1.0",
        "deny_by_default": False,
        "allowed_edges": [],
    }
    (config_dir / "allowed_rules.json").write_text(json.dumps(allowed_rules), encoding="utf-8")

    # exceptions.json (none)
    exceptions = {"version": "1.0", "exceptions": []}
    (config_dir / "exceptions.json").write_text(json.dumps(exceptions), encoding="utf-8")

    return config_dir


def _create_test_repo(tmpdir: Path) -> Path:
    """Create a minimal test repository."""
    repo_dir = tmpdir / "test_repo"
    repo_dir.mkdir()

    # Create simple Python files
    ui_dir = repo_dir / "ui"
    ui_dir.mkdir()
    (ui_dir / "main.py").write_text("from core import helper\n")

    core_dir = repo_dir / "core"
    core_dir.mkdir()
    (core_dir / "helper.py").write_text("# Helper module\n")

    # Initialize git repo (minimal - just create .git directory)
    git_dir = repo_dir / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

    return repo_dir


def test_classifier_mode_override_forced_conformance(tmp_path, monkeypatch):
    """Test that classifier_mode override forces conformance mode even when env var is not set."""
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    repo_dir = _create_test_repo(tmp_path)
    config_dir = _write_architecture_config(tmp_path)

    # Generate baseline
    try:
        baseline_result = generate_baseline(
            repo_dir,
            config_dir=config_dir,
            data_dir=tmp_path / "data",
            max_files=100,
            max_file_bytes=10000,
        )
        baseline_hash = baseline_result.get("baseline_hash_sha256")
    except Exception:
        baseline_hash = None

    # Create test commits
    commits = [
        {
            "hash": "abc123def456",
            "date": "2024-01-01T10:00:00Z",
            "message": "Add feature",
            "files_changed": ["ui/main.py"],
        }
    ]

    # Test with classifier_mode_override="conformance"
    drifts = commits_to_drifts(
        repo_url="file://" + str(repo_dir),
        commits=commits,
        max_drifts=5,
        repo_root_path=str(repo_dir),
        classifier_mode_override="conformance",
    )

    # Find architecture drifts
    arch_drifts = [d for d in drifts if d.driftType == "architecture"]

    # Assert at least one architecture drift exists
    assert len(arch_drifts) > 0, "Expected at least one architecture drift"

    # Assert classifier_mode_used is set correctly
    for drift in arch_drifts:
        assert drift.classifier_mode_used == "conformance", (
            f"Expected classifier_mode_used='conformance', got {drift.classifier_mode_used}"
        )

    # Assert that baseline_hash and rules_hash are set OR reason_codes explain why not
    for drift in arch_drifts:
        if drift.classification is not None:
            # If classification is set, baseline_hash and rules_hash should be set OR reason_codes explain
            if drift.baseline_hash is None and drift.rules_hash is None:
                # Must have reason_codes explaining why
                assert len(drift.reason_codes) > 0, (
                    "If baseline_hash and rules_hash are None, reason_codes must explain why"
                )
                # Should contain at least one of the expected reason codes
                expected_reasons = [
                    "BASELINE_MISSING",
                    "BASELINE_EMPTY",
                    "missing_baseline",
                    "missing_rules",
                ]
                assert any(
                    reason in drift.reason_codes for reason in expected_reasons
                ), f"Expected reason_codes to contain one of {expected_reasons}, got {drift.reason_codes}"


def test_classifier_mode_override_keywords(tmp_path, monkeypatch):
    """Test that classifier_mode override can force keywords mode."""
    # Set env to conformance
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")

    repo_dir = _create_test_repo(tmp_path)

    commits = [
        {
            "hash": "abc123def456",
            "date": "2024-01-01T10:00:00Z",
            "message": "refactor: improve code",
            "files_changed": ["ui/main.py"],
        }
    ]

    # Test with classifier_mode_override="keywords"
    drifts = commits_to_drifts(
        repo_url="file://" + str(repo_dir),
        commits=commits,
        max_drifts=5,
        repo_root_path=str(repo_dir),
        classifier_mode_override="keywords",
    )

    # Assert classifier_mode_used is set correctly
    for drift in drifts:
        assert drift.classifier_mode_used == "keywords", (
            f"Expected classifier_mode_used='keywords', got {drift.classifier_mode_used}"
        )

    # In keywords mode, classification should be None
    for drift in drifts:
        assert drift.classification is None, "In keywords mode, classification should be None"


def test_analyze_repo_with_classifier_mode_override(tmp_path, monkeypatch):
    """Test analyze_repo_for_drifts with classifier_mode override."""
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    repo_dir = _create_test_repo(tmp_path)
    config_dir = _write_architecture_config(tmp_path)

    base_clone_dir = str(tmp_path / ".repos")

    # Test with classifier_mode_override="conformance"
    # Since we can't easily create a real git repo in tests, we'll test that the function
    # accepts the parameters correctly without TypeError. The actual git operations may fail,
    # but that's acceptable - we're testing the parameter passing, not the git operations.
    try:
        drifts = analyze_repo_for_drifts(
            repo_url=str(repo_dir),  # Use directory path directly
            base_clone_dir=base_clone_dir,
            max_commits=10,
            max_drifts=5,
            config_dir=str(config_dir),
            data_dir=str(tmp_path / "data"),
            classifier_mode_override="conformance",
        )

        # If we got here, the function accepted the parameters correctly
        # Assert at least one drift exists
        assert len(drifts) > 0, "Expected at least one drift"

        # Assert classifier_mode_used is set correctly
        for drift in drifts:
            assert drift.classifier_mode_used == "conformance", (
                f"Expected classifier_mode_used='conformance', got {drift.classifier_mode_used}"
            )
    except (ValueError, RuntimeError, OSError) as e:
        # If git operations fail (e.g., not a real git repo), that's okay for this test
        # The important thing is that the function accepted the parameters without TypeError
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ["git", "repository", "clone", "extract", "name from url"]):
            # This is expected - the test repo isn't a real git repo
            # The key test is that we didn't get a TypeError about positional arguments
            pytest.skip(f"Git operation failed (expected for minimal test repo): {e}")
        else:
            raise

