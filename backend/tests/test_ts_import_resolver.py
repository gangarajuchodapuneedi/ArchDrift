from pathlib import Path

from utils.ts_import_resolver import (
    match_tsconfig_paths,
    resolve_ts_specifier_to_candidates,
)


def test_match_tsconfig_paths_longest_prefix():
    paths_map = {
        "@app/*": ["src/*"],
        "@app/test/*": ["test/*"],
    }
    matches = match_tsconfig_paths("@app/test/foo", paths_map)
    mapped = [m for _, m in matches]
    assert mapped == ["test/foo"]


def test_resolve_ts_specifier_to_candidates(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tsconfig = {
        "tsconfig_dir": repo,
        "baseUrl": ".",
        "paths": {"@/*": ["src/*"]},
    }
    spec = "@/core/b"
    candidates = resolve_ts_specifier_to_candidates(
        repo_root=repo, tsconfig=tsconfig, spec=spec
    )
    assert candidates
    assert repo / "src/core/b" in candidates

