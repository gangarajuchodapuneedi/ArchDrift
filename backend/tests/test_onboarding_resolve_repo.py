"""Tests for the onboarding resolve-repo endpoint.

These tests verify that the POST /onboarding/resolve-repo endpoint correctly
clones/opens a repository and returns the resolved local path.
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from git import Repo

from main import app


def test_onboarding_resolve_repo(tmp_path):
    """Test POST /onboarding/resolve-repo with a local git repository."""
    # Create a temporary directory for the test repository
    tmp_repo_dir = tmp_path / "test_repo"
    tmp_repo_dir.mkdir()

    # Initialize git repository
    repo = Repo.init(tmp_repo_dir)
    repo.config_writer().set_value("user", "name", "Tester").release()
    repo.config_writer().set_value("user", "email", "tester@example.com").release()

    # Create at least one file and commit it
    test_file = tmp_repo_dir / "test.txt"
    test_file.write_text("Test content\n", encoding="utf-8")
    repo.git.add("--all")
    repo.index.commit("Initial commit")

    # Call the endpoint
    client = TestClient(app)
    response = client.post(
        "/onboarding/resolve-repo",
        json={"repo_url": str(tmp_repo_dir)},
    )

    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Assert response JSON has required keys
    data = response.json()
    assert "repo_url" in data, "Response should have 'repo_url' field"
    assert "repo_path" in data, "Response should have 'repo_path' field"
    assert "repo_name" in data, "Response should have 'repo_name' field"

    # Assert repo_url matches input
    assert data["repo_url"] == str(tmp_repo_dir), "repo_url should match input"

    # Assert repo_path exists
    repo_path = Path(data["repo_path"])
    assert repo_path.exists(), f"Repository path should exist: {repo_path}"

    # Assert it is a git repository
    assert (repo_path / ".git").exists(), f"Repository path should contain .git directory: {repo_path}"

    # Cleanup: remove cloned repo path if it's different from source
    if repo_path.exists() and repo_path != tmp_repo_dir:
        shutil.rmtree(repo_path, ignore_errors=True)

