"""Tests for commit-level delta extractor using git blobs (no checkout)."""

from pathlib import Path

import pytest
from git import Repo

from utils.git_commit_graph import build_commit_delta, Limits
from utils.architecture_config import ArchitectureConfig, ModuleSpec, AllowedEdge, ExceptionEdge


def _config():
    return ArchitectureConfig(
        version="1.0",
        unmapped_module_id="unmapped",
        modules=[ModuleSpec(id="ui", roots=["ui"]), ModuleSpec(id="core", roots=["core"])],
        deny_by_default=True,
        allowed_edges=[],
        exceptions=[],
    )


def _init_repo(tmp_path: Path) -> Repo:
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Tester").release()
    repo.config_writer().set_value("user", "email", "tester@example.com").release()
    return repo


def _commit(repo: Repo, message: str):
    repo.git.add("--all")
    repo.index.commit(message)
    return repo.head.commit


def test_added_import_creates_edge(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "ui").mkdir()
    (tmp_path / "core").mkdir()
    (tmp_path / "ui" / "app.py").write_text("pass\n", encoding="utf-8")
    first = _commit(repo, "init")

    (tmp_path / "ui" / "app.py").write_text("from core import svc\n", encoding="utf-8")
    second = _commit(repo, "add import")

    result = build_commit_delta(str(tmp_path), second.hexsha, _config(), Limits())
    assert result["parent"] == first.hexsha
    assert result["edges_added"] == [{"from": "ui", "to": "core"}]
    assert result["edges_removed"] == []
    assert result["edges_added_count"] == 1
    assert any(ev["direction"] == "added" for ev in result["evidence"])


def test_removed_import_creates_edges_removed(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "ui").mkdir()
    (tmp_path / "core").mkdir()
    (tmp_path / "ui" / "app.py").write_text("from core import svc\n", encoding="utf-8")
    first = _commit(repo, "init with import")

    (tmp_path / "ui" / "app.py").write_text("pass\n", encoding="utf-8")
    second = _commit(repo, "remove import")

    result = build_commit_delta(str(tmp_path), second.hexsha, _config(), Limits())
    assert result["parent"] == first.hexsha
    assert result["edges_added"] == []
    assert result["edges_removed"] == [{"from": "ui", "to": "core"}]
    assert result["edges_removed_count"] == 1
    assert any(ev["direction"] == "removed" for ev in result["evidence"])


def test_non_code_file_ignored(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    first = _commit(repo, "init")
    (tmp_path / "README.md").write_text("world\n", encoding="utf-8")
    second = _commit(repo, "update readme")

    result = build_commit_delta(str(tmp_path), second.hexsha, _config(), Limits())
    assert result["parent"] == first.hexsha
    assert result["edges_added_count"] == 0
    assert result["edges_removed_count"] == 0


def test_binary_file_skipped(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "bin.py").write_bytes(b"\x00\x01\x02")
    commit = _commit(repo, "binary file")

    result = build_commit_delta(str(tmp_path), commit.hexsha, _config(), Limits())
    assert result["edges_added_count"] == 0
    assert result["stats"]["files_skipped_binary"] > 0


def test_rename_changes_from_module(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "ui").mkdir()
    (tmp_path / "core").mkdir()
    (tmp_path / "ui" / "app.js").write_text("import './local.js'\n", encoding="utf-8")
    (tmp_path / "ui" / "local.js").write_text("// none\n", encoding="utf-8")
    first = _commit(repo, "init ui")

    # Rename to core/app.js (from_module changes)
    (tmp_path / "core").mkdir(exist_ok=True)
    (tmp_path / "core" / "app.js").write_text("import '../ui/local.js'\n", encoding="utf-8")
    (tmp_path / "ui" / "app.js").unlink()
    second = _commit(repo, "rename to core")

    result = build_commit_delta(str(tmp_path), second.hexsha, _config(), Limits())
    assert result["parent"] == first.hexsha
    # from ui->ui becomes core->ui after rename; expect removal and addition
    assert {"from": "ui", "to": "ui"} in result["edges_removed"]
    assert {"from": "core", "to": "ui"} in result["edges_added"]
    assert result["edges_added_count"] >= 1
    assert result["edges_removed_count"] >= 1


def test_deterministic_output(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "ui").mkdir()
    (tmp_path / "core").mkdir()
    (tmp_path / "ui" / "app.ts").write_text("import '../core/svc'\n", encoding="utf-8")
    commit = _commit(repo, "one import")

    cfg = _config()
    result1 = build_commit_delta(str(tmp_path), commit.hexsha, cfg, Limits())
    result2 = build_commit_delta(str(tmp_path), commit.hexsha, cfg, Limits())
    assert result1["edges_added"] == result2["edges_added"]
    assert result1["evidence"] == result2["evidence"]

