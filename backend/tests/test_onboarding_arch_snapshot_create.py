"""Tests for the onboarding architecture-snapshot/create endpoint.

These tests verify that the POST /onboarding/architecture-snapshot/create endpoint correctly
creates content-addressed, immutable architecture snapshots.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from git import Repo

from main import app


def test_onboarding_arch_snapshot_create_happy_path(tmp_path):
    """Test POST /onboarding/architecture-snapshot/create creates snapshot successfully."""
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
    
    # Create config_dir with module_map.json
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    module_map = {
        "version": "1.0",
        "unmapped_module_id": "unmapped",
        "modules": [
            {"id": "src_core", "roots": ["src/core"]}
        ]
    }
    module_map_path = config_dir / "module_map.json"
    with open(module_map_path, "w", encoding="utf-8") as f:
        json.dump(module_map, f, indent=2, sort_keys=True)
    
    # Call the endpoint
    client = TestClient(app)
    response = client.post(
        "/onboarding/architecture-snapshot/create",
        json={
            "repo_path": str(repo_root),
            "config_dir": str(config_dir),
            "snapshot_label": "v1",
            "created_by": "tester",
            "note": "n",
        },
    )
    
    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Assert response JSON has required keys
    data = response.json()
    required_keys = {
        "repo_path",
        "repo_id",
        "snapshot_id",
        "snapshot_dir",
        "module_map_sha256",
        "rules_hash",
        "baseline_hash",
        "created_at_utc",
        "is_new",
    }
    assert set(data.keys()) == required_keys, f"Response should have exact keys: {required_keys}, got: {set(data.keys())}"
    
    # Assert repo_path matches input
    assert data["repo_path"] == str(repo_root), "repo_path should match input"
    
    # Assert repo_id is 12 characters hex
    assert isinstance(data["repo_id"], str), "repo_id should be a string"
    assert len(data["repo_id"]) == 12, "repo_id should be 12 characters"
    assert all(c in "0123456789abcdef" for c in data["repo_id"]), "repo_id should be hexadecimal"
    
    # Assert snapshot_id is 16 characters hex
    assert isinstance(data["snapshot_id"], str), "snapshot_id should be a string"
    assert len(data["snapshot_id"]) == 16, "snapshot_id should be 16 characters"
    assert all(c in "0123456789abcdef" for c in data["snapshot_id"]), "snapshot_id should be hexadecimal"
    
    # Assert snapshot_dir exists
    snapshot_dir = Path(data["snapshot_dir"])
    assert snapshot_dir.exists(), f"snapshot_dir should exist: {snapshot_dir}"
    assert snapshot_dir.is_dir(), f"snapshot_dir should be a directory: {snapshot_dir}"
    
    # Assert snapshot_dir contains module_map.json and metadata.json
    snapshot_module_map_path = snapshot_dir / "module_map.json"
    metadata_path = snapshot_dir / "metadata.json"
    assert snapshot_module_map_path.exists(), f"module_map.json should exist: {snapshot_module_map_path}"
    assert metadata_path.exists(), f"metadata.json should exist: {metadata_path}"
    
    # Assert module_map_sha256 matches computed SHA256
    with open(module_map_path, "rb") as f:
        file_bytes = f.read()
    expected_sha256 = hashlib.sha256(file_bytes).hexdigest()
    assert data["module_map_sha256"] == expected_sha256, f"module_map_sha256 should match computed SHA256: {data['module_map_sha256']} != {expected_sha256}"
    
    # Assert metadata.json fields match request and computed values
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    assert metadata["snapshot_id"] == data["snapshot_id"], "metadata snapshot_id should match response"
    assert metadata["repo_id"] == data["repo_id"], "metadata repo_id should match response"
    assert metadata["repo_path"] == str(repo_root), "metadata repo_path should match input"
    assert metadata["config_dir"] == str(config_dir), "metadata config_dir should match input"
    assert metadata["module_map_sha256"] == data["module_map_sha256"], "metadata module_map_sha256 should match response"
    assert metadata["snapshot_label"] == "v1", "metadata snapshot_label should match input"
    assert metadata["created_by"] == "tester", "metadata created_by should match input"
    assert metadata["note"] == "n", "metadata note should match input"
    assert metadata["created_at_utc"] == data["created_at_utc"], "metadata created_at_utc should match response"
    assert metadata["snapshot_id"] != "", "snapshot_id should not be empty"
    assert metadata["repo_id"] != "", "repo_id should not be empty"
    assert metadata["module_map_sha256"] != "", "module_map_sha256 should not be empty"
    
    # Assert is_new is True
    assert data["is_new"] is True, "is_new should be True for first creation"
    
    # Assert rules_hash and baseline_hash are None (no rules/baseline in test setup)
    assert data["rules_hash"] is None, "rules_hash should be None when allowed_rules.json doesn't exist"
    assert data["baseline_hash"] is None, "baseline_hash should be None when baseline doesn't exist"


def test_onboarding_arch_snapshot_create_idempotent(tmp_path):
    """Test that calling the endpoint again with same content returns same snapshot_id and is_new=false."""
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
    
    # Create config_dir with module_map.json
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    module_map = {
        "version": "1.0",
        "unmapped_module_id": "unmapped",
        "modules": [
            {"id": "src_core", "roots": ["src/core"]}
        ]
    }
    module_map_path = config_dir / "module_map.json"
    with open(module_map_path, "w", encoding="utf-8") as f:
        json.dump(module_map, f, indent=2, sort_keys=True)
    
    # Call the endpoint first time
    client = TestClient(app)
    response1 = client.post(
        "/onboarding/architecture-snapshot/create",
        json={
            "repo_path": str(repo_root),
            "config_dir": str(config_dir),
            "snapshot_label": "v1",
            "created_by": "tester",
            "note": "n",
        },
    )
    
    assert response1.status_code == 200, f"Expected 200, got {response1.status_code}: {response1.text}"
    data1 = response1.json()
    snapshot_id1 = data1["snapshot_id"]
    assert data1["is_new"] is True, "First call should have is_new=True"
    
    # Call the endpoint second time with same content
    response2 = client.post(
        "/onboarding/architecture-snapshot/create",
        json={
            "repo_path": str(repo_root),
            "config_dir": str(config_dir),
            "snapshot_label": "v1",
            "created_by": "tester",
            "note": "n",
        },
    )
    
    assert response2.status_code == 200, f"Expected 200, got {response2.status_code}: {response2.text}"
    data2 = response2.json()
    snapshot_id2 = data2["snapshot_id"]
    
    # Assert snapshot_id is identical
    assert snapshot_id2 == snapshot_id1, f"snapshot_id should be identical: {snapshot_id2} != {snapshot_id1}"
    
    # Assert is_new is False
    assert data2["is_new"] is False, "Second call should have is_new=False"


def test_onboarding_arch_snapshot_create_missing_module_map(tmp_path):
    """Test that missing module_map.json returns 400."""
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
    
    # Create config_dir WITHOUT module_map.json
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Do not create module_map.json
    
    # Call the endpoint
    client = TestClient(app)
    response = client.post(
        "/onboarding/architecture-snapshot/create",
        json={
            "repo_path": str(repo_root),
            "config_dir": str(config_dir),
        },
    )
    
    # Assert status code is 400
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    
    # Assert error message mentions module_map.json
    error_detail = response.json().get("detail", "")
    assert "module_map.json" in error_detail, f"Error message should mention module_map.json: {error_detail}"

