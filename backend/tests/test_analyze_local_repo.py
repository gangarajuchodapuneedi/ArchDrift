"""Tests for the analyze-local endpoint.

These tests verify that the POST /analyze-local endpoint correctly
analyzes a local repository path without cloning.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app


def test_post_analyze_local_invalid_classifier_mode_returns_422(tmp_path):
    """Test that invalid classifier_mode returns 422."""
    # Create a temporary directory so repo_path validation passes
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    client = TestClient(app)
    response = client.post(
        "/analyze-local",
        json={
            "repo_path": str(repo_dir),
            "classifier_mode": "bad",
        },
    )

    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
    assert "Invalid classifier_mode" in response.json()["detail"]


def test_post_analyze_local_missing_repo_path_returns_400(tmp_path):
    """Test that missing repo_path returns 400."""
    client = TestClient(app)
    non_existent_path = tmp_path / "does_not_exist"
    
    response = client.post(
        "/analyze-local",
        json={
            "repo_path": str(non_existent_path),
        },
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert "does not exist" in response.json()["detail"]


def test_post_analyze_local_keywords_happy_path_uses_no_clone(tmp_path):
    """Test keywords mode happy path uses no clone."""
    # Create a temporary directory (doesn't need to be a real git repo)
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Create a fake commit dict
    fake_commit = {
        "hash": "abc123",
        "date": "2024-01-01T00:00:00Z",
        "message": "Test commit",
        "files_changed": ["test.py"],
    }

    # Create a fake Drift object
    from models.drift import Drift

    fake_drift = Drift(
        id="test-001",
        date="2024-01-01T00:00:00Z",
        type="negative",
        title="Test drift",
        summary="Test",
        functionality="Test",
        files_changed=[],
        commit_hash="abc123",
        repo_url=f"local:{repo_dir}",
        classifier_mode_used="keywords",
    )

    # Mock list_commits and commits_to_drifts
    with patch("api.routes.list_commits", return_value=[fake_commit]) as mock_list_commits:
        with patch("api.routes.commits_to_drifts", return_value=[fake_drift]) as mock_commits_to_drifts:
            client = TestClient(app)
            response = client.post(
                "/analyze-local",
                json={
                    "repo_path": str(repo_dir),
                    "max_commits": 10,
                    "max_drifts": 5,
                    "classifier_mode": "keywords",
                },
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1

            # Assert returned drift has repo_url starting with "local:"
            drift = data[0]
            assert drift["repo_url"].startswith("local:")

            # Assert commits_to_drifts was called with correct repo_root_path
            mock_commits_to_drifts.assert_called_once()
            call_kwargs = mock_commits_to_drifts.call_args[1]
            assert call_kwargs["repo_root_path"] == str(repo_dir)
            assert call_kwargs["repo_url"] == f"local:{repo_dir}"


def test_post_analyze_local_conformance_invalid_config_dir_returns_400(tmp_path):
    """Test that invalid config_dir in conformance mode returns 400."""
    # Create a temporary directory for repo
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Use a non-existent config_dir
    non_existent_config = tmp_path / "does_not_exist"

    client = TestClient(app)
    response = client.post(
        "/analyze-local",
        json={
            "repo_path": str(repo_dir),
            "classifier_mode": "conformance",
            "config_dir": str(non_existent_config),
        },
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert "config_dir does not exist" in response.json()["detail"]

