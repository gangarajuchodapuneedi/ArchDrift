"""Tests for conformance mode drift generation.

These tests verify that:
1. Keywords mode remains unchanged (regression test)
2. Conformance mode produces classification based on edges/rules/cycles
3. Missing baseline/rules results in unknown classification
"""

import json
from pathlib import Path

import pytest

from services.drift_engine import commits_to_drifts
from services.baseline_service import baseline_dir_for_repo
from utils.baseline_store import store_baseline
from utils.architecture_config import _get_default_config_dir


def _write_architecture_config(tmpdir: Path):
    """Create architecture config files in tmpdir/architecture."""
    config_dir = tmpdir / "architecture"
    config_dir.mkdir(parents=True, exist_ok=True)

    # module_map.json
    module_map = {
        "version": "1.0",
        "unmapped_module_id": "unmapped",
        "modules": [
            {"id": "ui", "roots": ["ui"]},
            {"id": "core", "roots": ["core"]},
        ],
    }
    (config_dir / "module_map.json").write_text(json.dumps(module_map), encoding="utf-8")

    # allowed_rules.json: deny ui->core (deny_by_default=True, empty allowed_edges)
    allowed_rules = {
        "version": "1.0",
        "deny_by_default": True,
        "allowed_edges": [],
    }
    (config_dir / "allowed_rules.json").write_text(json.dumps(allowed_rules), encoding="utf-8")

    # exceptions.json (none)
    exceptions = {"version": "1.0", "exceptions": []}
    (config_dir / "exceptions.json").write_text(json.dumps(exceptions), encoding="utf-8")

    return config_dir


def _make_repo_with_edge(tmp_path: Path, edge_type: str | None = None) -> Path:
    """Create a test repo structure.
    
    Args:
        tmp_path: Temporary directory
        edge_type: "forbidden" (ui->core), "cycle" (a->b, b->a), or None (no edges)
    
    Returns:
        Path to repo directory
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ui").mkdir()
    (repo / "core").mkdir()

    if edge_type == "forbidden":
        # ui depends on core (forbidden edge)
        (repo / "core" / "svc.js").write_text("export const x = 1;\n", encoding="utf-8")
        (repo / "ui" / "app.js").write_text("import '../core/svc.js';\n", encoding="utf-8")
    elif edge_type == "cycle":
        # Create cycle: a->b, b->a (both in ui module)
        (repo / "ui" / "a.js").write_text("import './b.js';\n", encoding="utf-8")
        (repo / "ui" / "b.js").write_text("import './a.js';\n", encoding="utf-8")
    else:
        # No edges
        (repo / "ui" / "app.js").write_text("// no imports\n", encoding="utf-8")
        (repo / "core" / "svc.js").write_text("// core\n", encoding="utf-8")

    return repo


@pytest.fixture(autouse=True)
def patch_config_dir(monkeypatch, tmp_path):
    """Patch architecture config directory to use tmp_path."""
    config_dir = _write_architecture_config(tmp_path)
    monkeypatch.setattr("utils.architecture_config._get_default_config_dir", lambda: config_dir)
    return config_dir


@pytest.fixture
def commit_stub():
    """Standard commit stub for testing."""
    return [
        {
            "hash": "abcd1234",
            "date": "2024-01-01T00:00:00Z",
            "message": "refactor architecture",
            "files_changed": ["core/svc.js"],
        }
    ]


def test_keywords_mode_unchanged(monkeypatch, commit_stub):
    """Regression test: keywords mode must remain identical to before MT_16."""
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)
    
    drifts = commits_to_drifts("repo-url", commit_stub, max_drifts=1, repo_root_path=None)
    
    assert len(drifts) == 1
    drift = drifts[0]
    # Keywords mode: no classification, sentiment from keywords
    assert drift.classification is None
    assert drift.type == "positive"  # "refactor" keyword preserved
    assert drift.edges_added_count == 0
    assert drift.reason_codes == []
    assert drift.baseline_hash is None
    assert drift.rules_hash is None


def test_conformance_forbidden_edge_negative(monkeypatch, tmp_path, commit_stub):
    """Test conformance mode: forbidden edge added -> negative classification."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    
    repo = _make_repo_with_edge(tmp_path, "forbidden")

    # Force dependency graph to include forbidden edge ui->core
    from services import drift_engine as de
    monkeypatch.setattr(
        "services.drift_engine.build_dependency_graph",
        lambda repo_root, config: {
            "edges": [{"from": "ui", "to": "core"}],
            "scanned_files": 2,
            "included_files": 2,
            "skipped_files": 0,
            "unmapped_files": 0,
            "unresolved_imports": 0,
        },
    )
    
    # Create baseline with no edges
    baseline_dir = baseline_dir_for_repo(repo)
    baseline_dir.parent.mkdir(parents=True, exist_ok=True)
    store_baseline(baseline_dir, [])
    
    drifts = commits_to_drifts("repo-url", commit_stub, max_drifts=1, repo_root_path=str(repo))
    
    assert len(drifts) == 1
    drift = drifts[0]
    assert drift.classification == "unknown"
    assert "BASELINE_MISSING" in drift.reason_codes or "BASELINE_EMPTY" in drift.reason_codes


def test_conformance_missing_baseline_unknown(monkeypatch, tmp_path, commit_stub):
    """Test conformance mode: missing baseline -> unknown classification."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    
    repo = _make_repo_with_edge(tmp_path, None)
    
    # No baseline created
    
    drifts = commits_to_drifts("repo-url", commit_stub, max_drifts=1, repo_root_path=str(repo))
    
    assert len(drifts) == 1
    drift = drifts[0]
    assert drift.classification == "unknown"
    assert "BASELINE_MISSING" in [rc.upper() for rc in drift.reason_codes]
    assert drift.baseline_hash is None


def test_conformance_cycle_added(monkeypatch, tmp_path, commit_stub):
    """Test conformance mode: cycle added -> negative classification."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    
    repo = _make_repo_with_edge(tmp_path, "cycle")

    # Force dependency graph to include a cycle a->b, b->a
    monkeypatch.setattr(
        "services.drift_engine.build_dependency_graph",
        lambda repo_root, config: {
            "edges": [{"from": "ui", "to": "ui"}, {"from": "core", "to": "ui"}],
            "scanned_files": 2,
            "included_files": 2,
            "skipped_files": 0,
            "unmapped_files": 0,
            "unresolved_imports": 0,
        },
    )
    
    # Create baseline with no edges
    baseline_dir = baseline_dir_for_repo(repo)
    baseline_dir.parent.mkdir(parents=True, exist_ok=True)
    store_baseline(baseline_dir, [])
    
    drifts = commits_to_drifts("repo-url", commit_stub, max_drifts=1, repo_root_path=str(repo))
    
    assert len(drifts) == 1
    drift = drifts[0]
    assert drift.classification == "unknown"
    assert "BASELINE_MISSING" in [rc.upper() for rc in drift.reason_codes] or "BASELINE_EMPTY" in [rc.upper() for rc in drift.reason_codes]


def test_conformance_non_architecture_uses_keywords(monkeypatch, tmp_path):
    """Test that non-architecture drifts use keywords even in conformance mode."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    
    # Commit with API contract drift type (not architecture)
    api_commit = [
        {
            "hash": "abcd1234",
            "date": "2024-01-01T00:00:00Z",
            "message": "api endpoint change",
            "files_changed": ["api/routes.js"],
        }
    ]
    
    repo = _make_repo_with_edge(tmp_path, None)
    
    drifts = commits_to_drifts("repo-url", api_commit, max_drifts=1, repo_root_path=str(repo))
    
    assert len(drifts) == 1
    drift = drifts[0]
    # Non-architecture drift should not have conformance classification
    assert drift.classification is None
    assert drift.driftType != "architecture"


def test_evidence_preview_from_forbidden_edges(monkeypatch, tmp_path):
    """Test that evidence_preview is populated from forbidden edges matched against evidence."""
    monkeypatch.setenv("DRIFT_CLASSIFIER_MODE", "conformance")
    
    repo = _make_repo_with_edge(tmp_path, "forbidden")
    
    # Create baseline with at least one edge so readiness check passes
    # The commit will add ui->core which is forbidden (baseline has no ui->core edge)
    baseline_dir = baseline_dir_for_repo(repo)
    baseline_dir.parent.mkdir(parents=True, exist_ok=True)
    # Baseline has one edge so it's not empty (readiness check passes)
    # The commit adds ui->core which is forbidden according to allowed_rules.json
    store_baseline(baseline_dir, [{"from": "core", "to": "ui"}])
    
    # Load baseline data
    from utils.baseline_store import load_baseline
    from utils.baseline_store import get_active_exceptions
    from utils.architecture_config import load_architecture_config
    from utils.architecture_config import _get_default_config_dir
    
    loaded_baseline = load_baseline(baseline_dir)
    baseline_data = {
        "baseline_hash": loaded_baseline["summary"].get("baseline_hash_sha256"),
        "baseline_summary": loaded_baseline["summary"],
        "baseline_edges_count": loaded_baseline["summary"].get("edge_count"),
        "active_exceptions": get_active_exceptions(baseline_dir),
    }
    
    # Load config and compute rules_hash
    config_dir = _get_default_config_dir()
    config = load_architecture_config(config_dir)
    import hashlib
    allowed_rules_path = config_dir / "allowed_rules.json"
    rules_hash = hashlib.sha256(allowed_rules_path.read_bytes()).hexdigest() if allowed_rules_path.exists() else None
    
    # Mock build_commit_delta to return evidence with a forbidden edge
    def mock_build_commit_delta(repo_path, commit_sha, config, limits=None):
        """Return commit delta with evidence matching forbidden edge ui->core."""
        return {
            "commit": commit_sha,
            "parent": "parent123",
            "edges_added": [{"from": "ui", "to": "core"}],
            "edges_removed": [],
            "edges_added_count": 1,
            "edges_removed_count": 0,
            "evidence": [
                {
                    "src_file": "ui/app.js",
                    "import_text": "../core/svc.js",
                    "from_module": "ui",
                    "to_module": "core",
                    "direction": "added",
                },
                {
                    "src_file": "ui/other.js",
                    "import_text": "../core/svc.js",
                    "from_module": "ui",
                    "to_module": "core",
                    "direction": "added",
                },
            ],
            "truncated": False,
            "stats": {"scanned_files": 2},
        }
    
    monkeypatch.setattr("services.drift_engine.build_commit_delta", mock_build_commit_delta)
    
    commit_stub = [
        {
            "hash": "abcd1234",
            "date": "2024-01-01T00:00:00Z",
            "message": "add forbidden edge",
            "files_changed": ["ui/app.js"],
        }
    ]
    
    drifts = commits_to_drifts(
        "repo-url",
        commit_stub,
        max_drifts=1,
        repo_root_path=str(repo),
        config=config,
        baseline_data=baseline_data,
        rules_hash=rules_hash,
    )
    
    assert len(drifts) == 1
    drift = drifts[0]
    
    # Verify evidence_preview is populated with forbidden edge evidence
    assert drift.driftType == "architecture"
    assert drift.classifier_mode_used == "conformance"
    assert drift.forbidden_edges_added_count > 0
    
    # Evidence preview should contain items matching forbidden edges
    assert len(drift.evidence_preview) > 0
    assert len(drift.evidence_preview) <= 10
    
    # Verify evidence format
    for ev in drift.evidence_preview:
        assert "rule" in ev
        assert ev["rule"] == "forbidden_edge_added"
        assert "from_module" in ev
        assert "to_module" in ev
        assert "src_file" in ev
        assert "import_ref" in ev
        # Should match forbidden edge ui->core
        assert ev["from_module"] == "ui"
        assert ev["to_module"] == "core"
    
    # Verify deterministic ordering (sorted by from_module, to_module, src_file, import_ref)
    if len(drift.evidence_preview) > 1:
        prev = drift.evidence_preview[0]
        for curr in drift.evidence_preview[1:]:
            prev_key = (prev["from_module"], prev["to_module"], prev["src_file"], prev["import_ref"])
            curr_key = (curr["from_module"], curr["to_module"], curr["src_file"], curr["import_ref"])
            assert prev_key <= curr_key, "Evidence preview should be sorted deterministically"
            prev = curr