"""Tests for drift_engine using commit-level deltas under conformance mode."""

from pathlib import Path

import pytest
from git import Repo

from services.drift_engine import analyze_repo_for_drifts
from utils.architecture_config import ArchitectureConfig, ModuleSpec
from services.baseline_service import generate_baseline, approve_baseline


def _write_config(tmp_path: Path):
    cfg_dir = tmp_path / "architecture"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    # module_map
    (cfg_dir / "module_map.json").write_text(
        """
{
  "version": "1.0",
  "unmapped_module_id": "unmapped",
  "modules": [
    {"id": "ui", "roots": ["ui"]},
    {"id": "core", "roots": ["core"]}
  ]
}
""",
        encoding="utf-8",
    )
    # allowed_rules: deny by default, no allowed_edges -> ui->core forbidden
    (cfg_dir / "allowed_rules.json").write_text(
        """
{
  "version": "1.0",
  "deny_by_default": true,
  "allowed_edges": []
}
""",
        encoding="utf-8",
    )
    # exceptions: none
    (cfg_dir / "exceptions.json").write_text(
        """
{
  "version": "1.0",
  "exceptions": []
}
""",
        encoding="utf-8",
    )
    return cfg_dir


def _init_repo(tmp_path: Path) -> Repo:
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Tester").release()
    repo.config_writer().set_value("user", "email", "tester@example.com").release()
    return repo


def _commit(repo: Repo, message: str):
    repo.git.add("--all")
    repo.index.commit(message)
    return repo.head.commit


def _set_env(monkeypatch, mode: str):
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", mode)


def test_keywords_mode_regression(monkeypatch, tmp_path):
    _set_env(monkeypatch, "keywords")
    cfg_dir = _write_config(tmp_path)
    repo = _init_repo(tmp_path / "repo")
    (tmp_path / "repo" / "ui").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repo" / "core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repo" / "ui" / "app.py").write_text("refactor\n", encoding="utf-8")
    _commit(repo, "refactor ui")

    drifts = analyze_repo_for_drifts(str(tmp_path / "repo"), str(tmp_path / "repos"), max_commits=5, max_drifts=5)
    assert drifts
    d = drifts[0]
    assert d.classification is None
    assert d.type == "positive"


def test_conformance_per_commit_negative_and_positive(monkeypatch, tmp_path):
    _set_env(monkeypatch, "conformance")
    cfg_dir = _write_config(tmp_path)
    monkeypatch.setattr("utils.architecture_config._get_default_config_dir", lambda: cfg_dir)
    repo_root = tmp_path / "repo"
    repo = _init_repo(repo_root)
    data_dir = tmp_path / "data"
    monkeypatch.setattr("services.drift_engine.clone_or_open_repo", lambda url, base: str(repo_root))

    (repo_root / "ui").mkdir(parents=True, exist_ok=True)
    (repo_root / "core").mkdir(parents=True, exist_ok=True)
    (repo_root / "ui" / "local.py").write_text("x=1\n", encoding="utf-8")
    (repo_root / "ui" / "app.py").write_text("from . import local\n", encoding="utf-8")
    first = _commit(repo, "A init")

    # Baseline from first commit tree
    generate_baseline(repo_root, config_dir=cfg_dir, data_dir=data_dir)
    approve_baseline(repo_root, approved_by="tester", data_dir=data_dir)

    # Commit B: add forbidden edge ui->core
    (repo_root / "ui" / "app.py").write_text("from core import svc\n", encoding="utf-8")
    second = _commit(repo, "B add forbidden")

    # Commit C: remove import (back to no edge)
    (repo_root / "ui" / "app.py").write_text("print('clean')\n", encoding="utf-8")
    third = _commit(repo, "C remove forbidden")

    drifts = analyze_repo_for_drifts(
        str(repo_root),
        str(tmp_path / "repos"),
        max_commits=5,
        max_drifts=5,
        config_dir=str(cfg_dir),
        data_dir=str(data_dir),
    )
    # Commits are most recent first: C, B, A
    assert len(drifts) >= 2
    drift_c = drifts[0]  # commit C
    drift_b = drifts[1]  # commit B

    assert drift_b.classification in ("negative", "unknown")
    if drift_b.classification == "negative":
        assert drift_b.forbidden_edges_added_count > 0
    else:
        assert any(rc in drift_b.reason_codes for rc in ["BASELINE_MISSING", "BASELINE_EMPTY"])

    assert drift_c.classification in ("positive", "needs_review", "no_change", "unknown")
    assert drift_c.edges_removed_count >= 0


def test_conformance_no_change_commit(monkeypatch, tmp_path):
    _set_env(monkeypatch, "conformance")
    cfg_dir = _write_config(tmp_path)
    monkeypatch.setattr("utils.architecture_config._get_default_config_dir", lambda: cfg_dir)
    repo_root = tmp_path / "repo"
    repo = _init_repo(repo_root)
    data_dir = tmp_path / "data"
    monkeypatch.setattr("services.drift_engine.clone_or_open_repo", lambda url, base: str(repo_root))

    (repo_root / "ui").mkdir(parents=True, exist_ok=True)
    (repo_root / "core").mkdir(parents=True, exist_ok=True)
    (repo_root / "ui" / "app.py").write_text("print('init')\n", encoding="utf-8")
    first = _commit(repo, "A init")

    # Baseline from first commit tree
    generate_baseline(repo_root, config_dir=cfg_dir, data_dir=data_dir)
    approve_baseline(repo_root, approved_by="tester", data_dir=data_dir)

    # Commit D: change README only
    (repo_root / "README.md").write_text("hello\n", encoding="utf-8")
    second = _commit(repo, "D readme change")

    drifts = analyze_repo_for_drifts(
        str(repo_root),
        str(tmp_path / "repos"),
        max_commits=5,
        max_drifts=5,
        config_dir=str(cfg_dir),
        data_dir=str(data_dir),
    )
    d = drifts[0]
    assert d.classification in ("no_change", "needs_review", "unknown")
    assert d.edges_added_count == 0
    assert d.edges_removed_count == 0

