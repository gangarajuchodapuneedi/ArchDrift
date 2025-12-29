"""Tests for baseline status endpoint baseline_health field.

These tests verify that the GET /baseline/status endpoint correctly
includes the baseline_health field in the response.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from git import Repo

from main import app


def test_baseline_status_includes_baseline_health(tmp_path):
    """Test GET /baseline/status includes baseline_health field."""
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
    response = client.get(
        "/baseline/status",
        params={"repo_path": str(tmp_repo_dir)},
    )

    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Assert response JSON contains baseline_health key
    data = response.json()
    assert "baseline_health" in data, "Response should have 'baseline_health' field"

    # Assert baseline_health is a dict (can be empty {})
    assert isinstance(data["baseline_health"], dict), "baseline_health should be a dict"

