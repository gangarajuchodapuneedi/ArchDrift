"""Tests for rule checker utility.

These tests verify that check_rules() correctly identifies forbidden edges
and violations based on allowed_rules.json and active exceptions.
"""

from datetime import datetime, timedelta, timezone

import pytest

from utils.architecture_config import AllowedEdge, ArchitectureConfig, ModuleSpec
from utils.rule_checker import (
    build_allowed_set_from_rules,
    build_exception_set_and_map,
    check_rules,
)


def create_test_config(
    allowed_edges: list[AllowedEdge] | None = None, deny_by_default: bool = True
) -> ArchitectureConfig:
    """Create a test ArchitectureConfig."""
    if allowed_edges is None:
        allowed_edges = []

    return ArchitectureConfig(
        version="1.0",
        unmapped_module_id="unmapped",
        modules=[],
        deny_by_default=deny_by_default,
        allowed_edges=allowed_edges,
        exceptions=[],
    )


def test_allowed_edge_added():
    """Test that allowed edge added produces ok=true, no forbidden."""
    config = create_test_config(
        allowed_edges=[AllowedEdge(from_module="ui", to_module="core")]
    )
    compare_result = {
        "edges_added": [{"from": "ui", "to": "core"}],
        "edges_removed": [],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is True
    assert result["forbidden_edges_added"] == []
    assert result["forbidden_edges_removed"] == []
    assert result["allowed_via_exception"] == []
    assert result["violations"] == []
    assert result["counts"]["edges_added"] == 1
    assert result["counts"]["forbidden_added"] == 0
    assert result["error"] is None


def test_forbidden_edge_added():
    """Test that forbidden edge added produces ok=false, forbidden_edges_added contains it."""
    config = create_test_config(
        allowed_edges=[AllowedEdge(from_module="ui", to_module="core")]
    )
    compare_result = {
        "edges_added": [{"from": "ui", "to": "core"}, {"from": "api", "to": "db"}],
        "edges_removed": [],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is False
    assert result["forbidden_edges_added"] == [{"from": "api", "to": "db"}]
    assert result["forbidden_edges_removed"] == []
    assert result["allowed_via_exception"] == []
    assert len(result["violations"]) == 1
    assert result["violations"][0]["type"] == "forbidden_added"
    assert result["violations"][0]["edge"] == {"from": "api", "to": "db"}
    assert result["violations"][0]["rule_id"] is None
    assert result["counts"]["edges_added"] == 2
    assert result["counts"]["forbidden_added"] == 1
    assert result["error"] is None


def test_forbidden_edge_with_exception():
    """Test that forbidden edge but exception active produces ok=true, allowed_via_exception contains it."""
    config = create_test_config(
        allowed_edges=[AllowedEdge(from_module="ui", to_module="core")]
    )
    compare_result = {
        "edges_added": [{"from": "api", "to": "db"}],
        "edges_removed": [],
    }
    active_exceptions = [
        {
            "from_module": "api",
            "to_module": "db",
            "owner": "dev@example.com",
            "reason": "Temporary exception",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is True
    assert result["forbidden_edges_added"] == []
    assert result["forbidden_edges_removed"] == []
    assert result["allowed_via_exception"] == [{"from": "api", "to": "db"}]
    assert result["violations"] == []
    assert result["counts"]["edges_added"] == 1
    assert result["counts"]["forbidden_added"] == 0
    assert result["counts"]["exception_allowed"] == 1
    assert result["error"] is None


def test_expired_exception_ignored():
    """Test that expired exception doesn't suppress violation."""
    config = create_test_config(
        allowed_edges=[AllowedEdge(from_module="ui", to_module="core")]
    )
    compare_result = {
        "edges_added": [{"from": "api", "to": "db"}],
        "edges_removed": [],
    }
    # Expired exception (expires_at in the past)
    active_exceptions = [
        {
            "from_module": "api",
            "to_module": "db",
            "owner": "dev@example.com",
            "reason": "Expired exception",
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        }
    ]

    result = check_rules(compare_result, config, active_exceptions)

    # Note: expired exceptions should already be filtered by get_active_exceptions()
    # So if active_exceptions contains expired ones, they won't match
    # But if we pass them directly, they should be ignored
    assert result["ok"] is False
    assert result["forbidden_edges_added"] == [{"from": "api", "to": "db"}]
    assert result["allowed_via_exception"] == []
    assert len(result["violations"]) == 1


def test_deterministic_ordering():
    """Test that shuffled input produces same sorted output."""
    config = create_test_config(
        allowed_edges=[
            AllowedEdge(from_module="ui", to_module="core"),
            AllowedEdge(from_module="api", to_module="db"),
        ]
    )
    compare_result1 = {
        "edges_added": [
            {"from": "z", "to": "a"},
            {"from": "a", "to": "b"},
            {"from": "m", "to": "n"},
        ],
        "edges_removed": [],
    }
    compare_result2 = {
        "edges_added": [
            {"from": "m", "to": "n"},
            {"from": "z", "to": "a"},
            {"from": "a", "to": "b"},
        ],
        "edges_removed": [],
    }
    active_exceptions = []

    result1 = check_rules(compare_result1, config, active_exceptions)
    result2 = check_rules(compare_result2, config, active_exceptions)

    # Results should be identical (sorted)
    assert result1["forbidden_edges_added"] == result2["forbidden_edges_added"]
    assert result1["forbidden_edges_added"] == [
        {"from": "a", "to": "b"},
        {"from": "m", "to": "n"},
        {"from": "z", "to": "a"},
    ]


def test_deny_by_default():
    """Test that deny_by_default=True with empty allowed_edges makes all additions forbidden."""
    config = create_test_config(allowed_edges=[], deny_by_default=True)
    compare_result = {
        "edges_added": [{"from": "ui", "to": "core"}],
        "edges_removed": [],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is False
    assert result["forbidden_edges_added"] == [{"from": "ui", "to": "core"}]
    assert result["counts"]["forbidden_added"] == 1


def test_deny_by_default_false_allows_all():
    """Test that deny_by_default=False with empty allowed_edges allows all additions."""
    config = create_test_config(allowed_edges=[], deny_by_default=False)
    compare_result = {
        "edges_added": [{"from": "ui", "to": "core"}],
        "edges_removed": [],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is True
    assert result["forbidden_edges_added"] == []
    assert result["counts"]["forbidden_added"] == 0
    assert result["counts"]["edges_added"] == 1


def test_multiple_violations():
    """Test that multiple forbidden edges are all reported."""
    config = create_test_config(
        allowed_edges=[AllowedEdge(from_module="ui", to_module="core")]
    )
    compare_result = {
        "edges_added": [
            {"from": "ui", "to": "core"},  # Allowed
            {"from": "api", "to": "db"},  # Forbidden
            {"from": "web", "to": "auth"},  # Forbidden
        ],
        "edges_removed": [],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is False
    assert len(result["forbidden_edges_added"]) == 2
    assert {"from": "api", "to": "db"} in result["forbidden_edges_added"]
    assert {"from": "web", "to": "auth"} in result["forbidden_edges_added"]
    assert len(result["violations"]) == 2
    assert result["counts"]["forbidden_added"] == 2


def test_edges_removed_counted():
    """Test that edges_removed is included in counts even if not forbidden."""
    config = create_test_config(
        allowed_edges=[AllowedEdge(from_module="ui", to_module="core")]
    )
    compare_result = {
        "edges_added": [],
        "edges_removed": [{"from": "api", "to": "db"}],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is True  # No forbidden additions
    assert result["forbidden_edges_removed"] == []  # Always empty
    assert result["counts"]["edges_removed"] == 1
    assert result["counts"]["forbidden_removed"] == 0


def test_build_allowed_set_from_rules():
    """Test build_allowed_set_from_rules helper."""
    config = create_test_config(
        allowed_edges=[
            AllowedEdge(from_module="ui", to_module="core"),
            AllowedEdge(from_module="api", to_module="db"),
        ]
    )

    allowed_set = build_allowed_set_from_rules(config)

    assert allowed_set == {("ui", "core"), ("api", "db")}


def test_build_exception_set_and_map():
    """Test build_exception_set_and_map helper."""
    active_exceptions = [
        {
            "from_module": "ui",
            "to_module": "core",
            "owner": "dev@example.com",
            "reason": "Test exception",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }
    ]

    exception_set, exception_map = build_exception_set_and_map(active_exceptions)

    assert exception_set == {("ui", "core")}
    assert exception_map[("ui", "core")] == active_exceptions[0]


def test_build_exception_set_invalid_skipped():
    """Test that invalid exceptions (missing fields) are skipped."""
    active_exceptions = [
        {
            "from_module": "ui",
            "to_module": "core",
            "owner": "dev@example.com",
            "reason": "Valid",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
        {
            "from_module": "",  # Invalid - empty
            "to_module": "core",
            "owner": "dev@example.com",
            "reason": "Invalid",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
        {
            # Missing from_module
            "to_module": "core",
            "owner": "dev@example.com",
            "reason": "Invalid",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    ]

    exception_set, exception_map = build_exception_set_and_map(active_exceptions)

    # Only valid exception should be included
    assert exception_set == {("ui", "core")}
    assert len(exception_map) == 1


def test_invalid_edges_added():
    """Test that invalid edges_added format returns error object."""
    config = create_test_config()
    compare_result = {
        "edges_added": [{"from": "ui"}],  # Missing "to" key
        "edges_removed": [],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is False
    assert result["error"] is not None
    assert result["error"]["code"] == "invalid_edges_added"
    assert "missing required key 'to'" in result["error"]["message"]


def test_invalid_edges_removed():
    """Test that invalid edges_removed format returns error object."""
    config = create_test_config()
    compare_result = {
        "edges_added": [],
        "edges_removed": [{"to": "core"}],  # Missing "from" key
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is False
    assert result["error"] is not None
    assert result["error"]["code"] == "invalid_edges_removed"
    assert "missing required key 'from'" in result["error"]["message"]


def test_empty_inputs():
    """Test that empty inputs produce appropriate results."""
    config = create_test_config()
    compare_result = {
        "edges_added": [],
        "edges_removed": [],
    }
    active_exceptions = []

    result = check_rules(compare_result, config, active_exceptions)

    assert result["ok"] is True
    assert result["forbidden_edges_added"] == []
    assert result["forbidden_edges_removed"] == []
    assert result["allowed_via_exception"] == []
    assert result["violations"] == []
    assert result["counts"]["edges_added"] == 0
    assert result["counts"]["edges_removed"] == 0
    assert result["error"] is None

