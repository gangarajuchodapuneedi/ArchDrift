"""tsconfig/jsconfig loader with minimal JSONC support."""

from __future__ import annotations

import json
from pathlib import Path


def find_tsconfig(repo_root: Path) -> Path | None:
    """Return tsconfig.json or jsconfig.json under repo_root, preferring tsconfig."""
    ts_path = repo_root / "tsconfig.json"
    if ts_path.exists() and ts_path.is_file():
        return ts_path

    js_path = repo_root / "jsconfig.json"
    if js_path.exists() and js_path.is_file():
        return js_path

    return None


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments while preserving quoted strings."""
    result: list[str] = []
    i = 0
    state = "normal"

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if state == "normal":
            if ch == "/" and nxt == "/":
                result.append(" ")
                i += 1
                state = "line_comment"
            elif ch == "/" and nxt == "*":
                result.append(" ")
                i += 1
                state = "block_comment"
            elif ch == '"':
                result.append(ch)
                state = "double"
            elif ch == "'":
                result.append(ch)
                state = "single"
            elif ch == "`":
                result.append(ch)
                state = "template"
            else:
                result.append(ch)
        elif state == "line_comment":
            if ch == "\n":
                result.append(ch)
                state = "normal"
            else:
                result.append(" ")
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                result.append(" ")
                i += 1
                state = "normal"
            else:
                result.append(" ")
        elif state == "double":
            result.append(ch)
            if ch == "\\":
                if i + 1 < len(text):
                    i += 1
                    result.append(text[i])
            elif ch == '"':
                state = "normal"
        elif state == "single":
            result.append(ch)
            if ch == "\\":
                if i + 1 < len(text):
                    i += 1
                    result.append(text[i])
            elif ch == "'":
                state = "normal"
        elif state == "template":
            result.append(ch)
            if ch == "\\":
                if i + 1 < len(text):
                    i += 1
                    result.append(text[i])
            elif ch == "`":
                state = "normal"

        i += 1

    return "".join(result)


def _merge_compiler_options(base: dict, child: dict) -> dict:
    merged = {
        "baseUrl": base.get("baseUrl"),
        "paths": {},
    }

    base_paths = base.get("paths")
    if isinstance(base_paths, dict):
        for key, val in base_paths.items():
            if isinstance(key, str) and isinstance(val, list):
                merged["paths"][key] = [v for v in val if isinstance(v, str)]

    child_paths = child.get("paths")
    if isinstance(child_paths, dict):
        for key, val in child_paths.items():
            if isinstance(key, str) and isinstance(val, list):
                merged["paths"][key] = [v for v in val if isinstance(v, str)]

    if isinstance(child.get("baseUrl"), str):
        merged["baseUrl"] = child["baseUrl"]
    elif not isinstance(merged["baseUrl"], str):
        merged["baseUrl"] = None

    return merged


def _load_raw_config(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read tsconfig: {path}") from exc

    try:
        data = json.loads(strip_jsonc(text))
    except Exception as exc:
        raise ValueError(f"Invalid JSON in tsconfig: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"tsconfig root must be an object: {path}")
    return data


def load_tsconfig_compiler_options(tsconfig_path: Path, *, max_depth: int = 5) -> dict:
    """Load compilerOptions with extends support and normalized shapes."""
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    def _load(path: Path, depth: int) -> dict:
        if depth > max_depth:
            raise ValueError(f"tsconfig extends exceeds max_depth ({max_depth}) at {path}")

        data = _load_raw_config(path)
        extends_val = data.get("extends")
        compiler_opts = data.get("compilerOptions") or {}
        if not isinstance(compiler_opts, dict):
            raise ValueError(f"compilerOptions must be an object: {path}")

        base_opts: dict = {"baseUrl": None, "paths": {}}
        if isinstance(extends_val, str):
            base_path = (path.parent / extends_val).resolve()
            if not base_path.suffix:
                base_path = base_path.with_suffix(".json")
            if base_path.exists() and base_path.is_file():
                base_opts = _load(base_path, depth + 1)
            else:
                raise ValueError(f"extends target not found: {extends_val} (from {path})")

        merged = _merge_compiler_options(base_opts, compiler_opts)
        return merged | {"tsconfig_dir": path.parent}

    return _load(tsconfig_path.resolve(), 0)

