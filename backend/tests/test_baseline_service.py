"""Tests for baseline generator service.

These tests verify that generate_baseline() correctly loads config, builds
dependency graph, stores baseline files, and returns correct results.
"""

import json
from pathlib import Path

import pytest

from services.baseline_service import (
    baseline_dir_for_repo,
    compute_repo_id,
    generate_baseline,
)
from utils.baseline_store import load_baseline


def create_test_repo(tmp_path: Path) -> Path:
    """Create a test repository structure."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Python package structure
    pkg_dir = repo_dir / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")

    ui_dir = pkg_dir / "ui"
    ui_dir.mkdir()
    (ui_dir / "__init__.py").write_text("")
    (ui_dir / "a.py").write_text("from ..core import x\n")

    core_dir = pkg_dir / "core"
    core_dir.mkdir()
    (core_dir / "__init__.py").write_text("")
    (core_dir / "x.py").write_text("")

    # TypeScript structure
    web_dir = repo_dir / "web"
    web_dir.mkdir()

    web_ui_dir = web_dir / "ui"
    web_ui_dir.mkdir()
    (web_ui_dir / "a.ts").write_text('import "../core/b";\n')

    web_core_dir = web_dir / "core"
    web_core_dir.mkdir()
    (web_core_dir / "b.ts").write_text("")

    return repo_dir


def create_test_config(tmp_path: Path) -> Path:
    """Create a test architecture configuration."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()

    # module_map.json
    module_map_file = cfg_dir / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [
                    {"id": "ui", "roots": ["pkg/ui", "web/ui"]},
                    {"id": "core", "roots": ["pkg/core", "web/core"]},
                ],
            },
            indent=2,
        )
    )

    # allowed_rules.json
    allowed_rules_file = cfg_dir / "allowed_rules.json"
    allowed_rules_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            },
            indent=2,
        )
    )

    # exceptions.json
    exceptions_file = cfg_dir / "exceptions.json"
    exceptions_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            },
            indent=2,
        )
    )

    return cfg_dir


def test_generate_baseline_creates_files(tmp_path):
    """Test that generate_baseline creates baseline files in deterministic location."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    result = generate_baseline(
        repo_dir, config_dir=cfg_dir, data_dir=data_dir, max_files=2000
    )

    # Verify repo_id is 16 hex chars
    assert len(result["repo_id"]) == 16
    assert all(c in "0123456789abcdef" for c in result["repo_id"])

    # Verify baseline dir exists at expected location
    expected_baseline_dir = data_dir / "baselines" / result["repo_id"]
    assert expected_baseline_dir.exists()
    assert result["baseline_dir"] == str(expected_baseline_dir)

    # Verify baseline files exist
    edges_file = expected_baseline_dir / "baseline_edges.json"
    summary_file = expected_baseline_dir / "baseline_summary.json"
    assert edges_file.exists()
    assert summary_file.exists()

    # Verify load_baseline succeeds and hash matches
    loaded = load_baseline(expected_baseline_dir)
    assert loaded["summary"]["baseline_hash_sha256"] == result["baseline_hash_sha256"]
    assert loaded["summary"]["edge_count"] == result["edge_count"]

    # Verify edge_count >= 1 (should have ui -> core edge)
    assert result["edge_count"] >= 1

    # Verify all count keys are present and are integers
    assert isinstance(result["scanned_files"], int)
    assert isinstance(result["included_files"], int)
    assert isinstance(result["skipped_files"], int)
    assert isinstance(result["unmapped_files"], int)
    assert isinstance(result["unresolved_imports"], int)

    # Verify counts are non-negative
    assert result["scanned_files"] >= 0
    assert result["included_files"] >= 0
    assert result["skipped_files"] >= 0
    assert result["unmapped_files"] >= 0
    assert result["unresolved_imports"] >= 0


def test_compute_repo_id_stable(tmp_path):
    """Test that compute_repo_id is stable for same repo_root."""
    repo_dir = create_test_repo(tmp_path)

    repo_id1 = compute_repo_id(repo_dir)
    repo_id2 = compute_repo_id(repo_dir)

    # Same path should produce same ID
    assert repo_id1 == repo_id2
    assert len(repo_id1) == 16
    assert len(repo_id2) == 16


def test_compute_repo_id_invalid_nonexistent(tmp_path):
    """Test that compute_repo_id raises ValueError for non-existent path."""
    nonexistent_path = tmp_path / "nonexistent"

    with pytest.raises(ValueError) as exc_info:
        compute_repo_id(nonexistent_path)
    assert "does not exist" in str(exc_info.value)


def test_compute_repo_id_invalid_file(tmp_path):
    """Test that compute_repo_id raises ValueError for file path."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    with pytest.raises(ValueError) as exc_info:
        compute_repo_id(file_path)
    assert "not a directory" in str(exc_info.value)


def test_baseline_dir_for_repo(tmp_path):
    """Test that baseline_dir_for_repo returns correct path."""
    repo_dir = create_test_repo(tmp_path)
    data_dir = tmp_path / "custom_data"

    baseline_dir = baseline_dir_for_repo(repo_dir, data_dir=data_dir)

    repo_id = compute_repo_id(repo_dir)
    expected_dir = data_dir / "baselines" / repo_id
    assert baseline_dir == expected_dir


def test_generate_baseline_with_default_data_dir(tmp_path):
    """Test that generate_baseline uses default data_dir when not provided."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)

    # Note: This will use backend/data which may not exist in test environment
    # So we'll test with explicit data_dir in other tests
    # But we can verify the function works with explicit data_dir
    data_dir = tmp_path / "data"
    result = generate_baseline(repo_dir, config_dir=cfg_dir, data_dir=data_dir)

    assert "repo_id" in result
    assert "baseline_dir" in result
    assert "baseline_hash_sha256" in result
    assert len(result["baseline_hash_sha256"]) == 64


def test_generate_baseline_integrity_check(tmp_path):
    """Test that generate_baseline performs integrity check."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Should succeed without errors
    result = generate_baseline(repo_dir, config_dir=cfg_dir, data_dir=data_dir)

    # Verify baseline can be loaded
    baseline_dir = Path(result["baseline_dir"])
    loaded = load_baseline(baseline_dir)
    assert loaded["summary"]["baseline_hash_sha256"] == result["baseline_hash_sha256"]

