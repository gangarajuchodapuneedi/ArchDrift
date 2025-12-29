"""Tests for architecture configuration loader and validator.

These tests verify that load_architecture_config() correctly loads and validates
architecture configuration files with proper error handling.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from utils.architecture_config import (
    ArchitectureConfig,
    load_architecture_config,
)


def create_valid_module_map(tmp_path: Path) -> Path:
    """Create a valid module_map.json file."""
    file_path = tmp_path / "module_map.json"
    file_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [],
            },
            indent=2,
        )
    )
    return file_path


def create_valid_allowed_rules(tmp_path: Path) -> Path:
    """Create a valid allowed_rules.json file."""
    file_path = tmp_path / "allowed_rules.json"
    file_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            },
            indent=2,
        )
    )
    return file_path


def create_valid_exceptions(tmp_path: Path) -> Path:
    """Create a valid exceptions.json file."""
    file_path = tmp_path / "exceptions.json"
    file_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            },
            indent=2,
        )
    )
    return file_path


def test_load_valid_configs(tmp_path):
    """Test that valid sample configs can be loaded successfully."""
    create_valid_module_map(tmp_path)
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    config = load_architecture_config(tmp_path)

    assert isinstance(config, ArchitectureConfig)
    assert config.version == "1.0"
    assert config.unmapped_module_id == "unmapped"
    assert config.modules == []
    assert config.deny_by_default is True
    assert config.allowed_edges == []
    assert config.exceptions == []


def test_missing_module_map_raises_error(tmp_path):
    """Test that missing module_map.json raises ValueError with file name."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "module_map.json" in str(exc_info.value)
    assert "Missing configuration file" in str(exc_info.value) or "expected path" in str(
        exc_info.value
    )


def test_missing_allowed_rules_raises_error(tmp_path):
    """Test that missing allowed_rules.json raises ValueError with file name."""
    create_valid_module_map(tmp_path)
    create_valid_exceptions(tmp_path)

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "allowed_rules.json" in str(exc_info.value)
    assert "Missing configuration file" in str(exc_info.value) or "expected path" in str(
        exc_info.value
    )


def test_missing_exceptions_raises_error(tmp_path):
    """Test that missing exceptions.json raises ValueError with file name."""
    create_valid_module_map(tmp_path)
    create_valid_allowed_rules(tmp_path)

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "exceptions.json" in str(exc_info.value)
    assert "Missing configuration file" in str(exc_info.value) or "expected path" in str(
        exc_info.value
    )


def test_invalid_json_raises_error(tmp_path):
    """Test that invalid JSON raises ValueError mentioning file name."""
    create_valid_module_map(tmp_path)
    create_valid_allowed_rules(tmp_path)

    # Create invalid JSON file
    invalid_file = tmp_path / "exceptions.json"
    invalid_file.write_text("{ invalid json }")

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "exceptions.json" in str(exc_info.value)
    assert "Invalid JSON" in str(exc_info.value) or "JSON" in str(exc_info.value)


def test_duplicate_module_id_raises_error(tmp_path):
    """Test that duplicate module ID raises ValueError."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    # Create module_map with duplicate IDs
    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [
                    {"id": "module_a", "roots": ["path/a"]},
                    {"id": "module_a", "roots": ["path/b"]},
                ],
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "duplicate module id" in str(exc_info.value).lower()
    assert "module_a" in str(exc_info.value)


def test_modules_not_list_raises_error(tmp_path):
    """Test that modules not being a list raises ValueError."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": "not a list",
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "modules" in str(exc_info.value)
    assert "must be a list" in str(exc_info.value).lower()


def test_roots_not_list_raises_error(tmp_path):
    """Test that roots not being a list raises ValueError."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [{"id": "module_a", "roots": "not a list"}],
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "roots" in str(exc_info.value)
    assert "must be a list" in str(exc_info.value).lower()


def test_invalid_expires_on_date_raises_error(tmp_path):
    """Test that invalid expires_on date format raises ValueError."""
    create_valid_module_map(tmp_path)
    create_valid_allowed_rules(tmp_path)

    exceptions_file = tmp_path / "exceptions.json"
    exceptions_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [
                    {
                        "from": "module_a",
                        "to": "module_b",
                        "reason": "test",
                        "owner": "team",
                        "expires_on": "invalid-date",
                    }
                ],
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "expires_on" in str(exc_info.value)
    assert "ISO date" in str(exc_info.value) or "YYYY-MM-DD" in str(exc_info.value)


def test_cross_validate_unknown_module_in_allowed_edges_raises_error(tmp_path):
    """Test that allowed_edges referencing unknown module raises ValueError."""
    create_valid_exceptions(tmp_path)

    # Create module_map with one module
    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [{"id": "module_a", "roots": ["path/a"]}],
            },
            indent=2,
        )
    )

    # Create allowed_rules with reference to unknown module
    allowed_rules_file = tmp_path / "allowed_rules.json"
    allowed_rules_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [{"from": "module_a", "to": "unknown_module"}],
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "unknown module" in str(exc_info.value).lower()
    assert "unknown_module" in str(exc_info.value)
    assert "allowed_rules.json" in str(exc_info.value)


def test_cross_validate_unknown_module_in_exceptions_raises_error(tmp_path):
    """Test that exceptions referencing unknown module raises ValueError."""
    create_valid_allowed_rules(tmp_path)

    # Create module_map with one module
    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [{"id": "module_a", "roots": ["path/a"]}],
            },
            indent=2,
        )
    )

    # Create exceptions with reference to unknown module
    exceptions_file = tmp_path / "exceptions.json"
    exceptions_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [
                    {
                        "from": "module_a",
                        "to": "unknown_module",
                        "reason": "test",
                        "owner": "team",
                    }
                ],
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "unknown module" in str(exc_info.value).lower()
    assert "unknown_module" in str(exc_info.value)
    assert "exceptions.json" in str(exc_info.value)


def test_cross_validate_unmapped_module_id_allowed(tmp_path):
    """Test that references to unmapped_module_id are allowed."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    # Create module_map with one module
    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [{"id": "module_a", "roots": ["path/a"]}],
            },
            indent=2,
        )
    )

    # Create allowed_rules with reference to unmapped_module_id (should be allowed)
    allowed_rules_file = tmp_path / "allowed_rules.json"
    allowed_rules_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [{"from": "module_a", "to": "unmapped"}],
            },
            indent=2,
        )
    )

    # Should not raise an error
    config = load_architecture_config(tmp_path)
    assert len(config.allowed_edges) == 1
    assert config.allowed_edges[0].to_module == "unmapped"


def test_cross_validate_empty_modules_skips_validation(tmp_path):
    """Test that cross-validation is skipped when modules list is empty."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    # Create module_map with empty modules
    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [],
            },
            indent=2,
        )
    )

    # Create allowed_rules with reference to unknown module (should be allowed when modules is empty)
    allowed_rules_file = tmp_path / "allowed_rules.json"
    allowed_rules_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [{"from": "unknown_module", "to": "another_unknown"}],
            },
            indent=2,
        )
    )

    # Should not raise an error (cross-validation skipped)
    config = load_architecture_config(tmp_path)
    assert len(config.allowed_edges) == 1


def test_valid_expires_on_date_parsed_correctly(tmp_path):
    """Test that valid expires_on date is parsed correctly."""
    create_valid_module_map(tmp_path)
    create_valid_allowed_rules(tmp_path)

    exceptions_file = tmp_path / "exceptions.json"
    exceptions_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [
                    {
                        "from": "module_a",
                        "to": "module_b",
                        "reason": "test",
                        "owner": "team",
                        "expires_on": "2024-12-31",
                    }
                ],
            },
            indent=2,
        )
    )

    # This should work even with empty modules (cross-validation skipped)
    config = load_architecture_config(tmp_path)
    assert len(config.exceptions) == 1
    assert config.exceptions[0].expires_on == date(2024, 12, 31)


def test_path_resolution_works_from_different_directory(tmp_path, monkeypatch):
    """Test that path resolution works from different working directories."""
    create_valid_module_map(tmp_path)
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    # Change to a different directory
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)

    # Should still work when passing explicit config_dir
    config = load_architecture_config(tmp_path)
    assert isinstance(config, ArchitectureConfig)


def test_missing_required_keys_raises_error(tmp_path):
    """Test that missing required keys raise ValueError."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    # Create module_map missing 'version'
    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "unmapped_module_id": "unmapped",
                "modules": [],
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "version" in str(exc_info.value)
    assert "missing required key" in str(exc_info.value).lower()


def test_empty_string_values_raise_error(tmp_path):
    """Test that empty string values for required fields raise ValueError."""
    create_valid_allowed_rules(tmp_path)
    create_valid_exceptions(tmp_path)

    # Create module_map with empty unmapped_module_id
    module_map_file = tmp_path / "module_map.json"
    module_map_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "",
                "modules": [],
            },
            indent=2,
        )
    )

    with pytest.raises(ValueError) as exc_info:
        load_architecture_config(tmp_path)

    assert "unmapped_module_id" in str(exc_info.value)
    assert "must be non-empty" in str(exc_info.value).lower()

