"""Tests for baseline API endpoints.

These tests verify that the baseline API endpoints work correctly by testing
the underlying service functions that the endpoints call.
"""

import json
from pathlib import Path

import pytest

from datetime import datetime, timedelta, timezone

from services.baseline_service import approve_baseline, generate_baseline, get_baseline_status


def create_test_repo(tmp_path: Path) -> Path:
    """Create a test repository structure."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Python package structure
    pkg_dir = repo_dir / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")

    ui_dir = pkg_dir / "ui"
    ui_dir.mkdir()
    (ui_dir / "__init__.py").write_text("")
    (ui_dir / "a.py").write_text("from ..core import x\n")

    core_dir = pkg_dir / "core"
    core_dir.mkdir()
    (core_dir / "__init__.py").write_text("")
    (core_dir / "x.py").write_text("")

    # TypeScript structure
    web_dir = repo_dir / "web"
    web_dir.mkdir()

    web_ui_dir = web_dir / "ui"
    web_ui_dir.mkdir()
    (web_ui_dir / "a.ts").write_text('import "../core/b";\n')

    web_core_dir = web_dir / "core"
    web_core_dir.mkdir()
    (web_core_dir / "b.ts").write_text("")

    return repo_dir


def create_test_config(tmp_path: Path) -> Path:
    """Create a test architecture configuration."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()

    # module_map.json
    module_map_file = cfg_dir / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [
                    {"id": "ui", "roots": ["pkg/ui", "web/ui"]},
                    {"id": "core", "roots": ["pkg/core", "web/core"]},
                ],
            },
            indent=2,
        )
    )

    # allowed_rules.json
    allowed_rules_file = cfg_dir / "allowed_rules.json"
    allowed_rules_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            },
            indent=2,
        )
    )

    # exceptions.json
    exceptions_file = cfg_dir / "exceptions.json"
    exceptions_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            },
            indent=2,
        )
    )

    return cfg_dir


def test_get_baseline_status_missing(tmp_path):
    """Test baseline status when baseline is missing (simulates GET /baseline/status)."""
    repo_dir = create_test_repo(tmp_path)

    status_result = get_baseline_status(repo_dir)

    assert status_result["exists"] is False
    assert status_result["status"] == "missing"
    assert status_result["baseline_hash_sha256"] is None
    assert status_result["summary"] is None


def test_post_baseline_generate(tmp_path):
    """Test baseline generation (simulates POST /baseline/generate)."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    result = generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
        max_files=2000,
        max_file_bytes=200_000,
    )

    # Check status after generation
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["status"] == "draft"
    assert "baseline_hash_sha256" in result
    assert len(result["baseline_hash_sha256"]) == 64
    assert "edge_count" in result
    assert result["edge_count"] >= 1
    assert "scanned_files" in result
    assert "included_files" in result
    assert "skipped_files" in result
    assert "unmapped_files" in result
    assert "unresolved_imports" in result


def test_get_baseline_status_after_generate(tmp_path):
    """Test baseline status after generating baseline (simulates GET /baseline/status)."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Generate baseline first
    generate_result = generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )
    baseline_hash = generate_result["baseline_hash_sha256"]

    # Check status
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["exists"] is True
    assert status_result["status"] == "draft"
    assert status_result["baseline_hash_sha256"] == baseline_hash
    assert status_result["summary"] is not None
    assert status_result["summary"]["baseline_hash_sha256"] == baseline_hash


def test_generate_baseline_invalid_repo_path_nonexistent(tmp_path):
    """Test baseline generation with non-existent repo_path (simulates POST /baseline/generate error)."""
    nonexistent_path = tmp_path / "nonexistent"

    with pytest.raises(ValueError) as exc_info:
        generate_baseline(nonexistent_path)
    assert "does not exist" in str(exc_info.value)


def test_generate_baseline_invalid_repo_path_file(tmp_path):
    """Test baseline generation with file instead of directory (simulates POST /baseline/generate error)."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    with pytest.raises(ValueError) as exc_info:
        generate_baseline(file_path)
    assert "not a directory" in str(exc_info.value)


def test_get_baseline_status_invalid_repo_path_nonexistent(tmp_path):
    """Test baseline status with non-existent repo_path (simulates GET /baseline/status error)."""
    nonexistent_path = tmp_path / "nonexistent"

    with pytest.raises(ValueError) as exc_info:
        get_baseline_status(nonexistent_path)
    assert "does not exist" in str(exc_info.value)


def test_get_baseline_status_invalid_repo_path_file(tmp_path):
    """Test baseline status with file instead of directory (simulates GET /baseline/status error)."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    with pytest.raises(ValueError) as exc_info:
        get_baseline_status(file_path)
    assert "not a directory" in str(exc_info.value)


def test_generate_baseline_idempotent(tmp_path):
    """Test that calling generate twice produces same baseline hash."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Generate first time
    result1 = generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )
    hash1 = result1["baseline_hash_sha256"]

    # Generate second time (should be idempotent - same hash)
    result2 = generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )
    hash2 = result2["baseline_hash_sha256"]

    # Should produce same baseline hash (deterministic)
    assert hash1 == hash2


def test_approve_baseline_missing(tmp_path):
    """Test approve baseline when baseline is missing (simulates POST /baseline/approve error)."""
    repo_dir = create_test_repo(tmp_path)

    with pytest.raises(ValueError) as exc_info:
        approve_baseline(repo_dir, approved_by="test@example.com")
    assert "does not exist" in str(exc_info.value) or "generate baseline" in str(exc_info.value).lower()


def test_approve_baseline_success(tmp_path):
    """Test approve baseline success (simulates POST /baseline/approve)."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Generate baseline first
    generate_result = generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )
    baseline_hash = generate_result["baseline_hash_sha256"]

    # Approve baseline
    approve_result = approve_baseline(
        repo_dir,
        approved_by="test@example.com",
        approval_note="Approved for testing",
        data_dir=data_dir,
    )

    assert approve_result["status"] == "accepted"
    assert approve_result["approved_by"] == "test@example.com"
    assert approve_result["approved_at"] is not None
    assert approve_result["baseline_hash_sha256"] == baseline_hash
    assert approve_result["active_exceptions_count"] == 0

    # Check status shows accepted
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["status"] == "accepted"
    assert status_result["approved_by"] == "test@example.com"
    assert status_result["approved_at"] is not None
    assert status_result["active_exceptions_count"] == 0


def test_approve_with_exceptions(tmp_path):
    """Test approve baseline with exceptions."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Generate baseline
    generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )

    # Create exceptions with future expiry
    now = datetime.now(timezone.utc)
    future_expiry = (now + timedelta(days=30)).isoformat()

    exceptions = [
        {
            "from_module": "ui",
            "to_module": "core",
            "owner": "dev@example.com",
            "reason": "Temporary exception for refactoring",
            "expires_at": future_expiry,
        }
    ]

    # Approve with exceptions
    approve_result = approve_baseline(
        repo_dir,
        approved_by="reviewer@example.com",
        exceptions=exceptions,
        data_dir=data_dir,
    )

    assert approve_result["active_exceptions_count"] == 1

    # Check status includes exceptions count
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["active_exceptions_count"] == 1


def test_exception_expiry_filtering(tmp_path):
    """Test that expired exceptions are filtered out."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Generate baseline
    generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )

    # Create exceptions: one expired, one active
    now = datetime.now(timezone.utc)
    # For expired exception: created_at should be before expires_at, and expires_at should be in the past
    expired_created = (now - timedelta(days=2)).isoformat()  # Created 2 days ago
    expired_expires = (now - timedelta(days=1)).isoformat()  # Expired 1 day ago
    # For active exception: expires_at should be in the future
    active_created = now.isoformat()  # Created now
    active_expires = (now + timedelta(days=30)).isoformat()  # Expires in 30 days

    exceptions = [
        {
            "from_module": "ui",
            "to_module": "core",
            "owner": "dev@example.com",
            "reason": "Expired exception",
            "created_at": expired_created,
            "expires_at": expired_expires,
        },
        {
            "from_module": "api",
            "to_module": "db",
            "owner": "dev@example.com",
            "reason": "Active exception",
            "created_at": active_created,
            "expires_at": active_expires,
        },
    ]

    # Approve with both exceptions
    approve_result = approve_baseline(
        repo_dir,
        approved_by="reviewer@example.com",
        exceptions=exceptions,
        data_dir=data_dir,
    )

    # Only active exception should be counted
    assert approve_result["active_exceptions_count"] == 1

    # Check status
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["active_exceptions_count"] == 1


def test_approve_idempotent(tmp_path):
    """Test that approving twice remains accepted."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Generate baseline
    generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )

    # Approve first time
    approve_result1 = approve_baseline(
        repo_dir,
        approved_by="reviewer@example.com",
        data_dir=data_dir,
    )
    assert approve_result1["status"] == "accepted"

    # Approve second time (should remain accepted)
    approve_result2 = approve_baseline(
        repo_dir,
        approved_by="reviewer@example.com",
        data_dir=data_dir,
    )
    assert approve_result2["status"] == "accepted"

    # Status should still be accepted
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["status"] == "accepted"


def test_get_status_with_approval(tmp_path):
    """Test GET /baseline/status includes approval fields."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)
    data_dir = tmp_path / "data"

    # Generate baseline
    generate_baseline(
        repo_dir,
        config_dir=cfg_dir,
        data_dir=data_dir,
    )

    # Initially draft
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["status"] == "draft"
    assert status_result.get("approved_by") is None
    assert status_result.get("approved_at") is None
    assert status_result.get("active_exceptions_count") == 0

    # Approve
    approve_baseline(
        repo_dir,
        approved_by="reviewer@example.com",
        approval_note="Test approval",
        data_dir=data_dir,
    )

    # Check status includes approval fields
    status_result = get_baseline_status(repo_dir, data_dir=data_dir)
    assert status_result["status"] == "accepted"
    assert status_result["approved_by"] == "reviewer@example.com"
    assert status_result["approved_at"] is not None
    assert status_result["active_exceptions_count"] == 0

