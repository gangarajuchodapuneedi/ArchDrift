"""Tests for the onboarding architecture-snapshot/list endpoint.

These tests verify that the GET /onboarding/architecture-snapshot/list endpoint correctly
lists architecture snapshots for a repository, sorted by creation date descending.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from git import Repo

from main import app


def test_list_snapshots_sorted_desc(tmp_path):
    """Test GET /onboarding/architecture-snapshot/list returns snapshots sorted descending."""
    # Create a temporary directory for the test repository
    repo_root = tmp_path / "test_repo"
    repo_root.mkdir()
    
    # Create directory structure
    (repo_root / "src" / "core").mkdir(parents=True)
    
    # Create test file
    (repo_root / "src" / "core" / "a.py").write_text("# core a\n", encoding="utf-8")
    
    # Initialize git repository
    repo = Repo.init(repo_root)
    repo.config_writer().set_value("user", "name", "Tester").release()
    repo.config_writer().set_value("user", "email", "tester@example.com").release()
    
    # Commit at least one file
    repo.git.add("--all")
    repo.index.commit("Initial commit")
    
    # Compute repo_id using same algorithm as route
    repo_id = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]
    
    # Compute backend_dir the same way routes.py does
    backend_dir = Path(__file__).parent.parent
    
    # Create snapshots_root
    snapshots_root = backend_dir / ".onboarding" / "snapshots" / repo_id
    snapshots_root.mkdir(parents=True, exist_ok=True)
    
    # Create first snapshot directory (older, aaaa)
    snapshot_dir_1 = snapshots_root / "aaaaaaaaaaaaaaaa"
    snapshot_dir_1.mkdir()
    metadata_1 = {
        "snapshot_id": "aaaaaaaaaaaaaaaa",
        "created_at_utc": "2025-01-01T00:00:00Z",
        "snapshot_label": "v1",
        "created_by": "tester",
        "note": "n",
        "module_map_sha256": "h",
        "rules_hash": None,
        "baseline_hash": None,
    }
    with open(snapshot_dir_1 / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_1, f, indent=2, sort_keys=True)
    
    # Create second snapshot directory (newer, bbbb)
    snapshot_dir_2 = snapshots_root / "bbbbbbbbbbbbbbbb"
    snapshot_dir_2.mkdir()
    metadata_2 = {
        "snapshot_id": "bbbbbbbbbbbbbbbb",
        "created_at_utc": "2025-01-02T00:00:00Z",
        "snapshot_label": "v2",
        "created_by": "tester",
        "note": "n",
        "module_map_sha256": "h",
        "rules_hash": None,
        "baseline_hash": None,
    }
    with open(snapshot_dir_2 / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_2, f, indent=2, sort_keys=True)
    
    # Call the endpoint
    client = TestClient(app)
    response = client.get(
        "/onboarding/architecture-snapshot/list",
        params={"repo_path": str(repo_root), "limit": 20},
    )
    
    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Assert response JSON has required keys
    data = response.json()
    required_keys = {"repo_path", "repo_id", "snapshots"}
    assert set(data.keys()) == required_keys, f"Response should have exact keys: {required_keys}, got: {set(data.keys())}"
    
    # Assert repo_path matches input
    assert data["repo_path"] == str(repo_root), "repo_path should match input"
    
    # Assert repo_id matches computed value
    assert data["repo_id"] == repo_id, "repo_id should match computed value"
    
    # Assert snapshots array
    assert isinstance(data["snapshots"], list), "snapshots should be a list"
    assert len(data["snapshots"]) == 2, f"Expected 2 snapshots, got {len(data['snapshots'])}"
    
    # Assert snapshots are sorted descending (newer first)
    assert data["snapshots"][0]["snapshot_id"] == "bbbbbbbbbbbbbbbb", "First snapshot should be newer (bbbb)"
    assert data["snapshots"][1]["snapshot_id"] == "aaaaaaaaaaaaaaaa", "Second snapshot should be older (aaaa)"
    
    # Assert snapshot entry has exact keys
    snapshot_keys = {
        "snapshot_id",
        "created_at_utc",
        "snapshot_label",
        "created_by",
        "note",
        "module_map_sha256",
        "rules_hash",
        "baseline_hash",
    }
    for snapshot in data["snapshots"]:
        assert set(snapshot.keys()) == snapshot_keys, f"Snapshot should have exact keys: {snapshot_keys}, got: {set(snapshot.keys())}"
    
    # Cleanup: remove only the snapshots_root created for this test
    if snapshots_root.exists():
        shutil.rmtree(snapshots_root, ignore_errors=True)


def test_list_snapshots_limit_1(tmp_path):
    """Test GET /onboarding/architecture-snapshot/list respects limit parameter."""
    # Create a temporary directory for the test repository
    repo_root = tmp_path / "test_repo"
    repo_root.mkdir()
    
    # Create directory structure
    (repo_root / "src" / "core").mkdir(parents=True)
    
    # Create test file
    (repo_root / "src" / "core" / "a.py").write_text("# core a\n", encoding="utf-8")
    
    # Initialize git repository
    repo = Repo.init(repo_root)
    repo.config_writer().set_value("user", "name", "Tester").release()
    repo.config_writer().set_value("user", "email", "tester@example.com").release()
    
    # Commit at least one file
    repo.git.add("--all")
    repo.index.commit("Initial commit")
    
    # Compute repo_id using same algorithm as route
    repo_id = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]
    
    # Compute backend_dir the same way routes.py does
    backend_dir = Path(__file__).parent.parent
    
    # Create snapshots_root
    snapshots_root = backend_dir / ".onboarding" / "snapshots" / repo_id
    snapshots_root.mkdir(parents=True, exist_ok=True)
    
    # Create first snapshot directory (older, aaaa)
    snapshot_dir_1 = snapshots_root / "aaaaaaaaaaaaaaaa"
    snapshot_dir_1.mkdir()
    metadata_1 = {
        "snapshot_id": "aaaaaaaaaaaaaaaa",
        "created_at_utc": "2025-01-01T00:00:00Z",
        "snapshot_label": "v1",
        "created_by": "tester",
        "note": "n",
        "module_map_sha256": "h",
        "rules_hash": None,
        "baseline_hash": None,
    }
    with open(snapshot_dir_1 / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_1, f, indent=2, sort_keys=True)
    
    # Create second snapshot directory (newer, bbbb)
    snapshot_dir_2 = snapshots_root / "bbbbbbbbbbbbbbbb"
    snapshot_dir_2.mkdir()
    metadata_2 = {
        "snapshot_id": "bbbbbbbbbbbbbbbb",
        "created_at_utc": "2025-01-02T00:00:00Z",
        "snapshot_label": "v2",
        "created_by": "tester",
        "note": "n",
        "module_map_sha256": "h",
        "rules_hash": None,
        "baseline_hash": None,
    }
    with open(snapshot_dir_2 / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_2, f, indent=2, sort_keys=True)
    
    # Call the endpoint with limit=1
    client = TestClient(app)
    response = client.get(
        "/onboarding/architecture-snapshot/list",
        params={"repo_path": str(repo_root), "limit": 1},
    )
    
    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Assert response JSON
    data = response.json()
    assert isinstance(data["snapshots"], list), "snapshots should be a list"
    assert len(data["snapshots"]) == 1, f"Expected 1 snapshot with limit=1, got {len(data['snapshots'])}"
    
    # Assert it's the newest one
    assert data["snapshots"][0]["snapshot_id"] == "bbbbbbbbbbbbbbbb", "With limit=1, should return newest snapshot (bbbb)"
    
    # Cleanup: remove only the snapshots_root created for this test
    if snapshots_root.exists():
        shutil.rmtree(snapshots_root, ignore_errors=True)


def test_list_snapshots_invalid_repo_path_400(tmp_path):
    """Test GET /onboarding/architecture-snapshot/list returns 400 for invalid repo_path."""
    # Use a non-existent directory
    non_existent_path = tmp_path / "does_not_exist"
    
    # Call the endpoint
    client = TestClient(app)
    response = client.get(
        "/onboarding/architecture-snapshot/list",
        params={"repo_path": str(non_existent_path), "limit": 20},
    )
    
    # Assert status code is 400
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    
    # Assert error message mentions repo_path
    error_detail = response.json().get("detail", "")
    assert "repo_path" in error_detail.lower() or "invalid" in error_detail.lower(), f"Error message should mention repo_path or invalid: {error_detail}"

