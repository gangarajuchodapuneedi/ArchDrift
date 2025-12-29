"""Tests for the onboarding apply-module-map endpoint.

These tests verify that the POST /onboarding/apply-module-map endpoint correctly
persists a module_map.json file server-side and returns the config_dir path.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from git import Repo

from main import app


def test_onboarding_apply_module_map(tmp_path):
    """Test POST /onboarding/apply-module-map with a local git repository."""
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
    
    # Define module_map
    module_map = {
        "version": "1.0",
        "unmapped_module_id": "unmapped",
        "modules": [
            {"id": "src_core", "roots": ["src/core"]}
        ]
    }
    
    # Call the endpoint
    client = TestClient(app)
    response = client.post(
        "/onboarding/apply-module-map",
        json={
            "repo_path": str(repo_root),
            "module_map": module_map,
            "config_label": "suggested_v1"
        },
    )
    
    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Assert response JSON has required keys
    data = response.json()
    required_keys = {"repo_path", "repo_id", "config_dir", "module_map_path", "module_map_sha256", "notes"}
    assert set(data.keys()) == required_keys, f"Response should have exact keys: {required_keys}, got: {set(data.keys())}"
    
    # Assert repo_path matches input
    assert data["repo_path"] == str(repo_root), "repo_path should match input"
    
    # Assert repo_id is 12 characters hex
    assert isinstance(data["repo_id"], str), "repo_id should be a string"
    assert len(data["repo_id"]) == 12, "repo_id should be 12 characters"
    assert all(c in "0123456789abcdef" for c in data["repo_id"]), "repo_id should be hexadecimal"
    
    # Assert config_dir exists
    config_dir = Path(data["config_dir"])
    assert config_dir.exists(), f"config_dir should exist: {config_dir}"
    assert config_dir.is_dir(), f"config_dir should be a directory: {config_dir}"
    
    # Assert module_map_path exists
    module_map_path = Path(data["module_map_path"])
    assert module_map_path.exists(), f"module_map_path should exist: {module_map_path}"
    assert module_map_path.is_file(), f"module_map_path should be a file: {module_map_path}"
    
    # Assert module_map_path is inside config_dir
    assert module_map_path.parent == config_dir, f"module_map_path should be inside config_dir: {module_map_path.parent} != {config_dir}"
    
    # Read module_map_path JSON and assert it equals input module_map
    with open(module_map_path, "r", encoding="utf-8") as f:
        saved_module_map = json.load(f)
    
    assert saved_module_map == module_map, "Saved module_map should equal input module_map"
    
    # Assert module_map_sha256 matches sha256 of file bytes
    with open(module_map_path, "rb") as f:
        file_bytes = f.read()
    expected_sha256 = hashlib.sha256(file_bytes).hexdigest()
    assert data["module_map_sha256"] == expected_sha256, f"module_map_sha256 should match computed SHA256: {data['module_map_sha256']} != {expected_sha256}"
    
    # Assert notes
    assert isinstance(data["notes"], list), "notes should be a list"
    assert len(data["notes"]) > 0, "notes should not be empty"
    assert "Module map saved server-side (repo not modified)." in data["notes"], "notes should include expected message"
    
    # Verify repo was not modified (no module_map.json in repo)
    repo_module_map = repo_root / "module_map.json"
    assert not repo_module_map.exists(), "module_map.json should not exist in repo root"
    
    # Cleanup: delete the created config_dir
    if config_dir.exists():
        # Find backend directory
        backend_dir = Path(__file__).parent.parent
        onboarding_dir = backend_dir / ".onboarding"
        if onboarding_dir.exists():
            # Only delete the specific repo_id/label dir created by this test
            configs_dir = onboarding_dir / "configs"
            if configs_dir.exists():
                repo_id_dir = configs_dir / data["repo_id"]
                if repo_id_dir.exists():
                    shutil.rmtree(repo_id_dir, ignore_errors=True)

