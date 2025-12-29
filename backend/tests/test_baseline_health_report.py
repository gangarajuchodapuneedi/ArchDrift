import json
from pathlib import Path

import pytest

from services.baseline_service import get_baseline_status
from utils.baseline_store import load_baseline, store_baseline
from utils.dependency_graph import build_dependency_graph
from utils.architecture_config import load_architecture_config


def create_config(tmp_path: Path, modules: list[dict]) -> Path:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "module_map.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "unmapped_module_id": "unmapped",
                "modules": modules,
            },
            indent=2,
        )
    )
    (cfg_dir / "allowed_rules.json").write_text(
        json.dumps({"version": "1.0", "deny_by_default": True, "allowed_edges": []}, indent=2)
    )
    (cfg_dir / "exceptions.json").write_text(json.dumps({"version": "1.0", "exceptions": []}, indent=2))
    return cfg_dir


def test_unmapped_buckets_extraction_and_cap(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    buckets = ["src/components", "src/core", "packages/ui"]
    for bucket in buckets:
        dir_path = repo / bucket
        dir_path.mkdir(parents=True)
        for i in range(2):
            (dir_path / f"f{i}.ts").write_text("import './x';\n")
    # extra bucket to test ordering
    more = repo / "src/extra"
    more.mkdir(parents=True)
    (more / "f0.ts").write_text("import './x';\n")

    cfg_dir = create_config(tmp_path, modules=[{"id": "mapped", "roots": ["mapped"]}])
    config = load_architecture_config(cfg_dir)
    graph = build_dependency_graph(repo, config, max_files=50)

    assert "unmapped_buckets" in graph
    buckets_out = graph["unmapped_buckets"]
    assert len(buckets_out) <= 10
    assert all("/" not in b["bucket"][-1:] for b in buckets_out)  # ensure no filenames
    # sorted desc by count: first bucket should have count >= next
    counts = [b["count"] for b in buckets_out]
    assert counts == sorted(counts, reverse=True)


def test_baseline_summary_health_does_not_change_hash(tmp_path: Path):
    baseline_dir = tmp_path / "baseline"
    edges = [{"from": "a", "to": "b"}]
    health1 = {
        "included_files": 10,
        "unmapped_files": 2,
        "unresolved_imports": 1,
        "unmapped_buckets": [{"bucket": "src/x", "count": 2}],
    }
    health2 = {
        "included_files": 20,
        "unmapped_files": 5,
        "unresolved_imports": 3,
        "unmapped_buckets": [{"bucket": "src/y", "count": 1}],
    }

    result1 = store_baseline(baseline_dir, edges, graph_stats=health1)
    hash1 = result1["baseline_hash_sha256"]
    result2 = store_baseline(baseline_dir, edges, graph_stats=health2)
    hash2 = result2["baseline_hash_sha256"]

    assert hash1 == hash2
    loaded = load_baseline(baseline_dir)
    assert loaded["summary"]["baseline_hash_sha256"] == hash1
    assert loaded["summary"]["health"]["unmapped_files"] == health2["unmapped_files"]


def test_status_includes_baseline_health_and_actions(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    from services import baseline_service as bs

    # Match baseline dir with computed repo_id
    repo_id = bs.compute_repo_id(repo_root)
    baseline_dir = tmp_path / "data" / "baselines" / repo_id
    baseline_dir.mkdir(parents=True)
    summary = {
        "version": "1.0",
        "created_at_utc": "2024-01-01T00:00:00Z",
        "baseline_hash_sha256": "a" * 64,
        "edge_count": 0,
        "health": {
            "edge_count": 0,
            "included_files": 10,
            "unmapped_files": 7,
            "unmapped_ratio": 0.7,
            "unresolved_imports": 2,
            "top_unmapped_buckets": [{"bucket": "src/app", "count": 5}],
        },
    }
    (baseline_dir / "baseline_summary.json").write_text(json.dumps(summary, indent=2))
    (baseline_dir / "baseline_edges.json").write_text(
        json.dumps({"version": "1.0", "edges": [{"from": "a", "to": "b"}]}, indent=2)
    )

    # Monkeypatch default_data_dir to point to our tmp data dir
    original_default_data_dir = bs.default_data_dir
    try:
        bs.default_data_dir = lambda: tmp_path / "data"  # type: ignore[assignment]
        status = bs.get_baseline_status(repo_root)
    finally:
        bs.default_data_dir = original_default_data_dir

    assert status["baseline_health"]["baseline_ready"] is False
    assert status["baseline_health"]["mapping_ready"] is False
    actions = status["baseline_health"]["next_actions"]
    assert any("module_map.json" in a for a in actions)
    assert any("unmapped" in a for a in actions)

