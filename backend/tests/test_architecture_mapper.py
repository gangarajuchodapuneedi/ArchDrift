"""Tests for architecture path-to-module mapper.

These tests verify that map_path_to_module_id() correctly maps file paths
to module IDs based on module roots, including longest-root matching and
path normalization.
"""

import json
from pathlib import Path

import pytest

from utils.architecture_config import ArchitectureConfig, ModuleSpec, load_architecture_config
from utils.architecture_mapper import map_path_to_module_id, normalize_repo_path


def create_module_map_config(tmp_path: Path, modules_data: list) -> Path:
    """Create a module_map.json file with given modules."""
    file_path = tmp_path / "module_map.json"
    file_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": modules_data,
            },
            indent=2,
        )
    )
    return file_path


def create_allowed_rules_config(tmp_path: Path) -> Path:
    """Create a minimal allowed_rules.json file."""
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


def create_exceptions_config(tmp_path: Path) -> Path:
    """Create a minimal exceptions.json file."""
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


def test_exact_root_match(tmp_path):
    """Test that exact root match returns correct module id."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src/ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("src/ui", config)

    assert result == "ui"


def test_prefix_match(tmp_path):
    """Test that prefix match returns correct module id."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src/ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("src/ui/components/button.tsx", config)

    assert result == "ui"


def test_longest_root_wins(tmp_path):
    """Test that longest root wins when multiple roots match."""
    create_module_map_config(
        tmp_path,
        [
            {"id": "base", "roots": ["src"]},
            {"id": "ui", "roots": ["src/ui"]},
        ],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("src/ui/x.ts", config)

    # Should return "ui" because "src/ui" is longer than "src"
    assert result == "ui"


def test_windows_separators(tmp_path):
    """Test that Windows path separators are normalized correctly."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src/ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("src\\ui\\x.ts", config)

    assert result == "ui"


def test_leading_dot_slash(tmp_path):
    """Test that leading './' is stripped and path matches."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src/ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("./src/ui/x.ts", config)

    assert result == "ui"


def test_leading_slash(tmp_path):
    """Test that leading '/' is stripped and path matches."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src/ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("/src/ui/x.ts", config)

    assert result == "ui"


def test_unmapped_empty_modules(tmp_path):
    """Test that empty modules list returns unmapped_module_id."""
    create_module_map_config(tmp_path, [])
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("any/path/file.ts", config)

    assert result == "unmapped"


def test_unmapped_no_match(tmp_path):
    """Test that path with no matching root returns unmapped_module_id."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src/ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("other/path/file.ts", config)

    assert result == "unmapped"


def test_invalid_empty_root_raises_error(tmp_path):
    """Test that empty root string raises ValueError."""
    # Create config directly with invalid empty root to test mapper's defensive validation
    # (loader would reject this, but mapper should also validate defensively)
    config = ArchitectureConfig(
        version="1.0",
        unmapped_module_id="unmapped",
        modules=[ModuleSpec(id="ui", roots=[""])],  # Invalid: empty root
        deny_by_default=True,
        allowed_edges=[],
        exceptions=[],
    )

    with pytest.raises(ValueError) as exc_info:
        map_path_to_module_id("any/path", config)

    assert "Empty root string" in str(exc_info.value)
    assert "ui" in str(exc_info.value)


def test_normalize_repo_path_backslashes():
    """Test that normalize_repo_path converts backslashes to forward slashes."""
    result = normalize_repo_path("src\\ui\\file.ts")
    assert result == "src/ui/file.ts"


def test_normalize_repo_path_leading_dot_slash():
    """Test that normalize_repo_path strips leading './'."""
    result = normalize_repo_path("./src/ui/file.ts")
    assert result == "src/ui/file.ts"


def test_normalize_repo_path_leading_slash():
    """Test that normalize_repo_path strips leading '/'."""
    result = normalize_repo_path("/src/ui/file.ts")
    assert result == "src/ui/file.ts"


def test_normalize_repo_path_duplicate_slashes():
    """Test that normalize_repo_path collapses duplicate slashes."""
    result = normalize_repo_path("src//ui//file.ts")
    assert result == "src/ui/file.ts"


def test_normalize_repo_path_path_object():
    """Test that normalize_repo_path accepts Path objects."""
    result = normalize_repo_path(Path("src/ui/file.ts"))
    assert result == "src/ui/file.ts"


def test_multiple_modules_same_root_length(tmp_path):
    """Test deterministic behavior when multiple modules have same root length."""
    create_module_map_config(
        tmp_path,
        [
            {"id": "module_a", "roots": ["src/a"]},
            {"id": "module_b", "roots": ["src/b"]},
        ],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)

    # Both have same length, should return first match found (deterministic)
    result_a = map_path_to_module_id("src/a/file.ts", config)
    result_b = map_path_to_module_id("src/b/file.ts", config)

    assert result_a == "module_a"
    assert result_b == "module_b"


def test_exact_match_vs_prefix_match(tmp_path):
    """Test that exact match works correctly (not requiring trailing slash)."""
    create_module_map_config(
        tmp_path,
        [{"id": "root_module", "roots": ["root"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)

    # Exact match
    result1 = map_path_to_module_id("root", config)
    assert result1 == "root_module"

    # Prefix match
    result2 = map_path_to_module_id("root/sub/file.ts", config)
    assert result2 == "root_module"


def test_path_with_duplicate_slashes_matches(tmp_path):
    """Test that paths with duplicate slashes normalize and match correctly."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src/ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("src//ui//file.ts", config)

    assert result == "ui"


def test_root_with_duplicate_slashes_matches(tmp_path):
    """Test that roots with duplicate slashes normalize and match correctly."""
    create_module_map_config(
        tmp_path,
        [{"id": "ui", "roots": ["src//ui"]}],
    )
    create_allowed_rules_config(tmp_path)
    create_exceptions_config(tmp_path)

    config = load_architecture_config(tmp_path)
    result = map_path_to_module_id("src/ui/file.ts", config)

    assert result == "ui"

