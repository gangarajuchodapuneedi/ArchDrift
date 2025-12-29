"""Tests for the onboarding effective-config endpoint.

These tests verify that the GET /onboarding/effective-config endpoint correctly
resolves the effective config_dir (snapshot directory) for a repository, either
by snapshot_id or by selecting the latest snapshot.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from git import Repo

from main import app
import api.routes as routes_mod


def test_effective_config_by_snapshot_id(tmp_path):
    """Test GET /onboarding/effective-config with specific snapshot_id."""
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
    
    # Compute backend_dir using routes module
    backend_dir = Path(routes_mod.__file__).parent.parent
    
    # Create snapshots_root
    snapshots_root = backend_dir / ".onboarding" / "snapshots" / repo_id
    snapshots_root.mkdir(parents=True, exist_ok=True)
    
    # Create first snapshot directory (aaaa)
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
    
    # Create module_map.json with deterministic content
    module_map_content = {"version": "1.0", "modules": []}
    module_map_bytes = json.dumps(module_map_content, indent=2, sort_keys=True).encode("utf-8")
    with open(snapshot_dir_1 / "module_map.json", "wb") as f:
        f.write(module_map_bytes)
    
    # Compute expected SHA256
    expected_sha256 = hashlib.sha256(module_map_bytes).hexdigest()
    
    # Call the endpoint
    client = TestClient(app)
    response = client.get(
        "/onboarding/effective-config",
        params={"repo_path": str(repo_root), "snapshot_id": "aaaaaaaaaaaaaaaa"},
    )
    
    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Assert response JSON has exact required keys
    data = response.json()
    required_keys = {
        "repo_path",
        "repo_id",
        "snapshot_id",
        "config_dir",
        "module_map_path",
        "module_map_sha256",
        "created_at_utc",
        "snapshot_label",
        "created_by",
        "note",
    }
    assert set(data.keys()) == required_keys, f"Response should have exact keys: {required_keys}, got: {set(data.keys())}"
    
    # Assert repo_path matches input
    assert data["repo_path"] == str(repo_root), "repo_path should match input"
    
    # Assert repo_id matches computed value
    assert data["repo_id"] == repo_id, "repo_id should match computed value"
    
    # Assert snapshot_id matches
    assert data["snapshot_id"] == "aaaaaaaaaaaaaaaa", "snapshot_id should match input"
    
    # Assert config_dir ends with snapshot_id
    assert data["config_dir"].endswith("aaaaaaaaaaaaaaaa"), "config_dir should end with snapshot_id"
    
    # Assert module_map_sha256 matches computed hash
    assert data["module_map_sha256"] == expected_sha256, "module_map_sha256 should match computed hash"
    
    # Cleanup: remove only the snapshots_root created for this test
    if snapshots_root.exists():
        shutil.rmtree(snapshots_root, ignore_errors=True)


def test_effective_config_latest_when_snapshot_id_missing(tmp_path):
    """Test GET /onboarding/effective-config without snapshot_id selects latest."""
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
    
    # Compute backend_dir using routes module
    backend_dir = Path(routes_mod.__file__).parent.parent
    
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
    
    # Create module_map.json
    module_map_content = {"version": "1.0", "modules": []}
    with open(snapshot_dir_1 / "module_map.json", "w", encoding="utf-8") as f:
        json.dump(module_map_content, f, indent=2, sort_keys=True)
    
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
    
    # Create module_map.json
    module_map_content = {"version": "1.0", "modules": []}
    with open(snapshot_dir_2 / "module_map.json", "w", encoding="utf-8") as f:
        json.dump(module_map_content, f, indent=2, sort_keys=True)
    
    # Call the endpoint without snapshot_id
    client = TestClient(app)
    response = client.get(
        "/onboarding/effective-config",
        params={"repo_path": str(repo_root)},
    )
    
    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Assert response JSON
    data = response.json()
    
    # Assert snapshot_id is the latest (bbbb)
    assert data["snapshot_id"] == "bbbbbbbbbbbbbbbb", "snapshot_id should be latest (bbbbbbbbbbbbbbbb)"
    
    # Cleanup: remove only the snapshots_root created for this test
    if snapshots_root.exists():
        shutil.rmtree(snapshots_root, ignore_errors=True)


def test_effective_config_invalid_snapshot_id_422(tmp_path):
    """Test GET /onboarding/effective-config returns 422 for invalid snapshot_id."""
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
    
    # Call the endpoint with invalid snapshot_id
    client = TestClient(app)
    response = client.get(
        "/onboarding/effective-config",
        params={"repo_path": str(repo_root), "snapshot_id": "BAD"},
    )
    
    # Assert status code is 422
    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
    
    # Assert error message mentions 16 lowercase hex chars
    error_detail = response.json().get("detail", "")
    assert "16 lowercase hex" in error_detail.lower(), f"Error message should mention 16 lowercase hex chars: {error_detail}"


def test_effective_config_no_snapshots_404(tmp_path):
    """Test GET /onboarding/effective-config returns 404 when no snapshots exist."""
    # Create a temporary directory for the test repository (different from other tests)
    repo_root = tmp_path / "test_repo_no_snapshots"
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
    
    # Do NOT create snapshots_root - it should not exist
    
    # Call the endpoint
    client = TestClient(app)
    response = client.get(
        "/onboarding/effective-config",
        params={"repo_path": str(repo_root)},
    )
    
    # Assert status code is 404
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    
    # Assert error message mentions snapshots
    error_detail = response.json().get("detail", "")
    assert "snapshot" in error_detail.lower(), f"Error message should mention snapshot: {error_detail}"

