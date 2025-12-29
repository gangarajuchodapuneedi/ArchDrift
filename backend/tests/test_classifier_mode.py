"""Tests for drift classifier mode environment variable parsing.

These tests verify that get_drift_classifier_mode() correctly reads and validates
the DRIFT_CLASSIFIER_MODE environment variable.
"""

import pytest
from services.drift_engine import get_drift_classifier_mode


def test_unset_env_var_returns_keywords(monkeypatch):
    """Test that unset env var returns 'keywords' (default)."""
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)
    assert get_drift_classifier_mode() == "keywords"


def test_keywords_mode_returns_keywords(monkeypatch):
    """Test that setting env var to 'keywords' returns 'keywords'."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "keywords")
    assert get_drift_classifier_mode() == "keywords"


def test_conformance_mode_returns_conformance(monkeypatch):
    """Test that setting env var to 'conformance' returns 'conformance'."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    assert get_drift_classifier_mode() == "conformance"


def test_uppercase_keywords_returns_keywords(monkeypatch):
    """Test that uppercase 'KEYWORDS' is normalized to 'keywords' (case insensitive)."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "KEYWORDS")
    assert get_drift_classifier_mode() == "keywords"


def test_invalid_value_returns_keywords(monkeypatch):
    """Test that invalid value (e.g., 'abc') returns 'keywords' without raising exception."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "abc")
    assert get_drift_classifier_mode() == "keywords"


def test_empty_string_returns_keywords(monkeypatch):
    """Test that empty string returns 'keywords'."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "")
    assert get_drift_classifier_mode() == "keywords"


def test_whitespace_returns_keywords(monkeypatch):
    """Test that whitespace-only value returns 'keywords'."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "   ")
    assert get_drift_classifier_mode() == "keywords"

