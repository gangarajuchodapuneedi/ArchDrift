"""Tests for the onboarding suggest-module-map endpoint.

These tests verify that the POST /onboarding/suggest-module-map endpoint correctly
suggests a module_map.json based on folder scan.
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from git import Repo

from main import app


def test_onboarding_suggest_module_map_folder_scan(tmp_path):
    """Test POST /onboarding/suggest-module-map with folder scan method."""
    # Create a temporary directory for the test repository
    repo_root = tmp_path / "test_repo"
    repo_root.mkdir()
    
    # Create directory structure
    (repo_root / "src" / "core").mkdir(parents=True)
    (repo_root / "src" / "ui").mkdir(parents=True)
    (repo_root / "tests").mkdir()
    (repo_root / "node_modules").mkdir()
    
    # Create test files
    (repo_root / "src" / "core" / "a.py").write_text("# core a\n", encoding="utf-8")
    (repo_root / "src" / "core" / "b.py").write_text("# core b\n", encoding="utf-8")
    (repo_root / "src" / "ui" / "u.ts").write_text("// ui u\n", encoding="utf-8")
    (repo_root / "tests" / "test_x.py").write_text("# test x\n", encoding="utf-8")
    (repo_root / "node_modules" / "ignore.js").write_text("// ignored\n", encoding="utf-8")
    
    # Initialize git repository
    repo = Repo.init(repo_root)
    repo.config_writer().set_value("user", "name", "Tester").release()
    repo.config_writer().set_value("user", "email", "tester@example.com").release()
    
    # Create at least one file and commit it
    test_file = repo_root / "src" / "core" / "a.py"
    repo.git.add("--all")
    repo.index.commit("Initial commit")
    
    # Call the endpoint
    client = TestClient(app)
    response = client.post(
        "/onboarding/suggest-module-map",
        json={"repo_path": str(repo_root), "max_modules": 5},
    )
    
    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Assert response JSON has required keys
    data = response.json()
    required_keys = {"repo_path", "suggestion_method", "buckets", "module_map_suggestion", "notes"}
    assert set(data.keys()) == required_keys, f"Response should have exact keys: {required_keys}, got: {set(data.keys())}"
    
    # Assert suggestion_method
    assert data["suggestion_method"] == "folder_scan", "suggestion_method should be 'folder_scan'"
    
    # Assert repo_path
    assert data["repo_path"] == str(repo_root), "repo_path should match input"
    
    # Assert buckets structure and content
    assert isinstance(data["buckets"], list), "buckets should be a list"
    
    # Find buckets by name
    buckets_dict = {b["bucket"]: b["file_count"] for b in data["buckets"]}
    
    # Assert src/core bucket exists with file_count 2
    assert "src/core" in buckets_dict, "buckets should include 'src/core'"
    assert buckets_dict["src/core"] == 2, "src/core should have file_count 2"
    
    # Assert src/ui bucket exists with file_count 1
    assert "src/ui" in buckets_dict, "buckets should include 'src/ui'"
    assert buckets_dict["src/ui"] == 1, "src/ui should have file_count 1"
    
    # Assert node_modules bucket never appears
    assert "node_modules" not in buckets_dict, "node_modules bucket should not appear"
    
    # Assert module_map_suggestion structure
    module_map = data["module_map_suggestion"]
    assert isinstance(module_map, dict), "module_map_suggestion should be a dict"
    assert module_map["version"] == "1.0", "module_map_suggestion.version should be '1.0'"
    assert module_map["unmapped_module_id"] == "unmapped", "module_map_suggestion.unmapped_module_id should be 'unmapped'"
    assert "modules" in module_map, "module_map_suggestion should have 'modules' key"
    assert isinstance(module_map["modules"], list), "module_map_suggestion.modules should be a list"
    
    # Assert modules contain expected IDs
    module_ids = [m["id"] for m in module_map["modules"]]
    
    # Check for sanitized src_core and src_ui (or similar)
    has_src_core = any("core" in mid for mid in module_ids)
    has_src_ui = any("ui" in mid for mid in module_ids)
    assert has_src_core, f"modules should contain a module with 'core' in id, got: {module_ids}"
    assert has_src_ui, f"modules should contain a module with 'ui' in id, got: {module_ids}"
    
    # Assert tests module exists
    tests_modules = [m for m in module_map["modules"] if "test" in m["id"].lower()]
    assert len(tests_modules) > 0, f"modules should include a tests module, got: {module_ids}"
    
    # Check tests module has correct roots
    tests_module = tests_modules[0]
    assert "roots" in tests_module, "tests module should have 'roots' key"
    assert isinstance(tests_module["roots"], list), "tests module roots should be a list"
    assert len(tests_module["roots"]) > 0, "tests module should have at least one root"
    assert tests_module["roots"][0] in ["tests", "src/tests"], f"tests module root should be 'tests' or 'src/tests', got: {tests_module['roots']}"
    
    # Assert notes
    assert isinstance(data["notes"], list), "notes should be a list"
    assert len(data["notes"]) > 0, "notes should not be empty"
    assert any("folder scan" in note.lower() for note in data["notes"]), "notes should mention folder scan"
    
    # Cleanup
    if repo_root.exists():
        shutil.rmtree(repo_root, ignore_errors=True)

