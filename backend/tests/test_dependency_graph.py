"""Tests for dependency graph builder.

These tests verify that build_dependency_graph() correctly scans a repository,
extracts relative imports, resolves them to target files, and builds a
module-level dependency graph.
"""

import json
from pathlib import Path

import pytest

from utils.architecture_config import load_architecture_config
from utils.dependency_graph import build_dependency_graph


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


def test_basic_dependency_graph(tmp_path):
    """Test that basic dependency graph is built correctly."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    # Check that edge ui -> core exists (from Python relative import)
    edges = result["edges"]
    assert {"from": "ui", "to": "core"} in edges


def test_ts_import_creates_edge(tmp_path):
    """Test that TS relative import creates edge (same as Python, deduplicated)."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    # Edge should exist from TS import
    edges = result["edges"]
    assert {"from": "ui", "to": "core"} in edges

    # Should only be one edge (deduplicated)
    ui_to_core_count = sum(1 for e in edges if e["from"] == "ui" and e["to"] == "core")
    assert ui_to_core_count == 1


def test_edges_unique_and_sorted(tmp_path):
    """Test that edges list is unique and sorted."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    edges = result["edges"]

    # Check uniqueness
    edge_set = {(e["from"], e["to"]) for e in edges}
    assert len(edge_set) == len(edges)

    # Check sorted (lexicographically by (from, to))
    sorted_edges = sorted(edges, key=lambda e: (e["from"], e["to"]))
    assert edges == sorted_edges


def test_evidence_structure(tmp_path):
    """Test that evidence contains correct structure."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    evidence = result["evidence"]
    assert len(evidence) > 0

    # Check at least one evidence item with ui -> core
    ui_to_core_evidence = [
        e
        for e in evidence
        if e["from_module"] == "ui" and e["to_module"] == "core"
    ]
    assert len(ui_to_core_evidence) > 0

    # Check evidence structure
    ev = ui_to_core_evidence[0]
    assert "from_file" in ev
    assert "to_file" in ev
    assert "import_ref" in ev
    assert "from_module" in ev
    assert "to_module" in ev
    assert "lang" in ev
    assert ev["lang"] in ("py", "tsjs")


def test_scanned_files_count(tmp_path):
    """Test that scanned_files and included_files are non-zero."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    assert result["scanned_files"] > 0
    assert result["included_files"] > 0
    assert result["scanned_files"] >= result["included_files"]


def test_unresolved_imports_zero(tmp_path):
    """Test that unresolved_imports is 0 for valid setup."""
    repo_dir = create_test_repo(tmp_path)
    cfg_dir = create_test_config(tmp_path)

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    assert result["unresolved_imports"] == 0


def test_bounds_max_files(tmp_path):
    """Test that max_files limit is enforced."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Create more than max_files dummy files
    max_files = 10
    for i in range(max_files + 5):
        file_path = repo_dir / f"file_{i}.py"
        file_path.write_text("")

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()

    # Minimal config
    (cfg_dir / "module_map.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [],
            },
            indent=2,
        )
    )
    (cfg_dir / "allowed_rules.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            },
            indent=2,
        )
    )
    (cfg_dir / "exceptions.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            },
            indent=2,
        )
    )

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config, max_files=max_files)

    assert result["scanned_files"] == max_files


def test_invalid_repo_root_raises_error(tmp_path):
    """Test that invalid repo_root raises ValueError."""
    cfg_dir = create_test_config(tmp_path)
    config = load_architecture_config(cfg_dir)

    # Non-existent path
    with pytest.raises(ValueError) as exc_info:
        build_dependency_graph(tmp_path / "nonexistent", config)
    assert "does not exist" in str(exc_info.value)

    # File instead of directory
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")
    with pytest.raises(ValueError) as exc_info:
        build_dependency_graph(file_path, config)
    assert "not a directory" in str(exc_info.value)


def test_ignored_directories(tmp_path):
    """Test that ignored directories are not scanned."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Create file in ignored directory
    node_modules = repo_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.js").write_text("import './x';")

    # Create file in regular directory
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("")

    cfg_dir = create_test_config(tmp_path)
    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    # Should not find file in node_modules
    evidence = result["evidence"]
    node_modules_files = [e for e in evidence if "node_modules" in e["from_file"]]
    assert len(node_modules_files) == 0


def test_file_size_limit(tmp_path):
    """Test that files exceeding max_file_bytes are skipped."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Create large file
    large_file = repo_dir / "large.py"
    large_content = "x" * 300_000  # Exceeds default 200_000 limit
    large_file.write_text(large_content)

    # Create normal file
    normal_file = repo_dir / "normal.py"
    normal_file.write_text("import os\n")

    cfg_dir = create_test_config(tmp_path)
    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config, max_file_bytes=200_000)

    assert result["skipped_files"] >= 1
    assert result["included_files"] >= 1


def test_relative_imports_only(tmp_path):
    """Test that only relative imports create edges."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("import os\nimport requests\nfrom .local import x\n")

    local_file = src_dir / "local.py"
    local_file.write_text("")

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()

    (cfg_dir / "module_map.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [{"id": "src", "roots": ["src"]}],
            },
            indent=2,
        )
    )
    (cfg_dir / "allowed_rules.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            },
            indent=2,
        )
    )
    (cfg_dir / "exceptions.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            },
            indent=2,
        )
    )

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    # Should not create edges from absolute imports (os, requests)
    # Only relative import (.local) should create edge if both files mapped
    edges = result["edges"]
    # Since both files are in "src" module, no edge should be created (same module)
    # But we can verify that absolute imports don't create edges
    assert all(e["from"] != "unmapped" and e["to"] != "unmapped" for e in edges)


def test_tsconfig_alias_import_creates_edge(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    (repo_dir / "tsconfig.json").write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "baseUrl": ".",
                    "paths": {"@/*": ["src/*"]},
                }
            }
        )
    )

    src_dir = repo_dir / "src"
    ui_dir = src_dir / "ui"
    core_dir = src_dir / "core"
    ui_dir.mkdir(parents=True)
    core_dir.mkdir(parents=True)

    (ui_dir / "a.ts").write_text('import x from "@/core/b";\n')
    (core_dir / "b.ts").write_text("export const b = 1;\n")

    cfg_dir = tmp_path / "cfg_alias"
    cfg_dir.mkdir()
    (cfg_dir / "module_map.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [
                    {"id": "ui", "roots": ["src/ui"]},
                    {"id": "core", "roots": ["src/core"]},
                ],
            }
        )
    )
    (cfg_dir / "allowed_rules.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            }
        )
    )
    (cfg_dir / "exceptions.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            }
        )
    )

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    edges = result["edges"]
    assert {"from": "ui", "to": "core"} in edges
    assert result["unresolved_imports"] == 0


def test_abs_import_without_tsconfig_skipped(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.ts").write_text('import React from "react";\n')

    cfg_dir = tmp_path / "cfg_abs"
    cfg_dir.mkdir()
    (cfg_dir / "module_map.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [{"id": "src", "roots": ["src"]}],
            }
        )
    )
    (cfg_dir / "allowed_rules.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            }
        )
    )
    (cfg_dir / "exceptions.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            }
        )
    )

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    assert result["edges"] == []
    assert result["unresolved_imports"] == 0


def test_python_absolute_import_src_layout(tmp_path):
    """Test that Python absolute imports in src-layout create edges."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Create src-layout structure
    src_dir = repo_dir / "src"
    src_dir.mkdir()

    mypkg_dir = src_dir / "mypkg"
    mypkg_dir.mkdir()

    core_dir = mypkg_dir / "core"
    core_dir.mkdir()
    (core_dir / "x.py").write_text("")

    ui_dir = mypkg_dir / "ui"
    ui_dir.mkdir()
    (ui_dir / "a.py").write_text("from mypkg.core import x\n")

    cfg_dir = tmp_path / "cfg_src"
    cfg_dir.mkdir()
    (cfg_dir / "module_map.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": [
                    {"id": "ui", "roots": ["src/mypkg/ui"]},
                    {"id": "core", "roots": ["src/mypkg/core"]},
                ],
            }
        )
    )
    (cfg_dir / "allowed_rules.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "deny_by_default": True,
                "allowed_edges": [],
            }
        )
    )
    (cfg_dir / "exceptions.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "exceptions": [],
            }
        )
    )

    config = load_architecture_config(cfg_dir)
    result = build_dependency_graph(repo_dir, config)

    # Assert edge ui -> core exists from absolute import
    edges = result["edges"]
    assert {"from": "ui", "to": "core"} in edges
    assert result["unresolved_imports"] == 0