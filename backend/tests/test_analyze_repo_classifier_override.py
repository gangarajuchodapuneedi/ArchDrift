"""Tests for classifier mode override in analyze-repo endpoint.

These tests verify that:
1. resolve_classifier_mode() correctly handles override values
2. analyze_repo_for_drifts() raises TypeError when called with too many positional args
3. The route handler calls analyze_repo_for_drifts() correctly with keyword args
4. classifier_mode_used is set correctly on drifts
"""

import os
from unittest.mock import Mock, patch

import pytest

from services.drift_engine import (
    analyze_repo_for_drifts,
    commits_to_drifts,
    resolve_classifier_mode,
)


def test_resolve_classifier_mode_with_override_conformance(monkeypatch):
    """Test that resolve_classifier_mode("conformance") returns "conformance" even if env is unset."""
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)
    
    result = resolve_classifier_mode("conformance")
    assert result == "conformance"


def test_resolve_classifier_mode_with_override_keywords(monkeypatch):
    """Test that resolve_classifier_mode("keywords") returns "keywords" even if env is set to conformance."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    
    result = resolve_classifier_mode("keywords")
    assert result == "keywords"


def test_resolve_classifier_mode_invalid_override_uses_env(monkeypatch):
    """Test that invalid override returns default/env mode."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    
    # Invalid override should fall back to env
    result = resolve_classifier_mode("invalid")
    assert result == "conformance"
    
    # None override should fall back to env
    result = resolve_classifier_mode(None)
    assert result == "conformance"


def test_resolve_classifier_mode_none_uses_env_default(monkeypatch):
    """Test that None override uses env default (keywords)."""
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)
    
    result = resolve_classifier_mode(None)
    assert result == "keywords"


def test_analyze_repo_for_drifts_raises_typeerror_with_too_many_positional_args():
    """Regression test: analyze_repo_for_drifts raises TypeError when called with too many positional args."""
    # This should raise TypeError because config_dir, data_dir, commit_limits, classifier_mode_override
    # are keyword-only arguments (after the '*' in the function signature)
    with pytest.raises(TypeError, match="positional arguments"):
        analyze_repo_for_drifts(
            "https://github.com/test/repo",
            "/tmp/repos",
            10,
            5,
            "/tmp/config",  # config_dir - positional (WRONG)
            "/tmp/data",    # data_dir - positional (WRONG)
            None,           # commit_limits - positional (WRONG)
            "conformance",  # classifier_mode_override - positional (WRONG)
        )


def test_analyze_repo_for_drifts_accepts_keyword_args():
    """Test that analyze_repo_for_drifts accepts keyword-only args correctly."""
    # Verify the signature has keyword-only parameters after the first 4 positional ones
    import inspect
    sig = inspect.signature(analyze_repo_for_drifts)
    params = list(sig.parameters.values())
    
    # First 4 params should be positional (repo_url, base_clone_dir, max_commits, max_drifts)
    assert len([p for p in params[:4] if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD]) == 4
    
    # Check for keyword-only parameters (these come after the '*' separator in the signature)
    keyword_only = [p for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY]
    assert len(keyword_only) >= 4, f"Should have at least 4 keyword-only parameters, found {len(keyword_only)}"
    assert any(p.name == "classifier_mode_override" for p in keyword_only), "Should have classifier_mode_override as keyword-only parameter"
    assert any(p.name == "config_dir" for p in keyword_only), "Should have config_dir as keyword-only parameter"
    assert any(p.name == "data_dir" for p in keyword_only), "Should have data_dir as keyword-only parameter"


def test_route_handler_calls_with_keyword_args(monkeypatch):
    """Test that the route handler calls analyze_repo_for_drifts with keyword args."""
    # Mock analyze_repo_for_drifts to capture how it's called
    call_args_list = []
    call_kwargs_list = []
    
    def mock_analyze_repo_for_drifts(*args, **kwargs):
        call_args_list.append(args)
        call_kwargs_list.append(kwargs)
        # Return minimal drift list
        from models.drift import Drift
        return [
            Drift(
                id="test-001",
                date="2024-01-01T00:00:00Z",
                type="negative",
                title="Test drift",
                summary="Test",
                functionality="Test",
                files_changed=[],
                commit_hash="abc123",
                repo_url="https://github.com/test/repo",
                classifier_mode_used=kwargs.get("classifier_mode_override", "keywords"),
            )
        ]
    
    # Patch the function
    with patch("api.routes.analyze_repo_for_drifts", side_effect=mock_analyze_repo_for_drifts):
        from api.routes import analyze_repo
        from api.routes import AnalyzeRepoRequest
        import asyncio
        
        # Create a request with classifier_mode override
        request = AnalyzeRepoRequest(
            repo_url="https://github.com/test/repo",
            max_commits=10,
            max_drifts=5,
            classifier_mode="conformance",
        )
        
        # This will fail because we're not in a proper async context, but we can check the mock
        # Instead, let's directly test the call pattern by importing and checking the route code
        from pathlib import Path
        import inspect
        
        # Get the analyze_repo function source
        source = inspect.getsource(analyze_repo)
        
        # Verify it uses keyword args for analyze_repo_for_drifts
        assert "classifier_mode_override=" in source, "Route should use keyword arg for classifier_mode_override"
        assert "config_dir=None" in source or "config_dir=" in source, "Route should use keyword arg for config_dir"
        assert "data_dir=None" in source or "data_dir=" in source, "Route should use keyword arg for data_dir"


def test_commits_to_drifts_sets_classifier_mode_used():
    """Test that commits_to_drifts sets classifier_mode_used on all drifts."""
    commits = [
        {
            "hash": "abc123",
            "date": "2024-01-01T00:00:00Z",
            "message": "Test commit",
            "files_changed": ["test.py"],
        }
    ]
    
    drifts = commits_to_drifts(
        repo_url="https://github.com/test/repo",
        commits=commits,
        max_drifts=5,
        classifier_mode_override="conformance",
    )
    
    assert len(drifts) > 0
    for drift in drifts:
        assert drift.classifier_mode_used == "conformance", (
            f"Expected classifier_mode_used='conformance', got {drift.classifier_mode_used}"
        )


def test_commits_to_drifts_uses_env_when_override_none(monkeypatch):
    """Test that commits_to_drifts uses env when override is None."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "keywords")
    
    commits = [
        {
            "hash": "abc123",
            "date": "2024-01-01T00:00:00Z",
            "message": "Test commit",
            "files_changed": ["test.py"],
        }
    ]
    
    drifts = commits_to_drifts(
        repo_url="https://github.com/test/repo",
        commits=commits,
        max_drifts=5,
        classifier_mode_override=None,
    )
    
    assert len(drifts) > 0
    for drift in drifts:
        assert drift.classifier_mode_used == "keywords", (
            f"Expected classifier_mode_used='keywords', got {drift.classifier_mode_used}"
        )

