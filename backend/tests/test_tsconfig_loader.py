import json
from pathlib import Path

import pytest

from utils.tsconfig_loader import load_tsconfig_compiler_options, strip_jsonc


def test_strip_jsonc_handles_comments():
    content = """
    {
      // line comment
      "compilerOptions": {
        /* block comment */
        "baseUrl": "."
      }
    }
    """
    parsed = json.loads(strip_jsonc(content))
    assert parsed["compilerOptions"]["baseUrl"] == "."


def test_load_tsconfig_with_extends_and_merge(tmp_path: Path):
    base = tmp_path / "base.json"
    base.write_text(
        """
        {
          "compilerOptions": {
            "baseUrl": "base",
            "paths": {
              "@app/*": ["base/*"]
            }
          }
        }
        """
    )

    child = tmp_path / "tsconfig.json"
    child.write_text(
        """
        {
          "extends": "./base.json",
          "compilerOptions": {
            "baseUrl": ".",
            "paths": {
              "@app/*": ["src/*"],
              "@app/test/*": ["test/*"]
            }
          }
        }
        """
    )

    result = load_tsconfig_compiler_options(child)
    assert result["tsconfig_dir"] == child.parent
    assert result["baseUrl"] == "."
    assert result["paths"]["@app/*"] == ["src/*"]
    assert result["paths"]["@app/test/*"] == ["test/*"]


def test_load_tsconfig_invalid_json_raises(tmp_path: Path):
    cfg = tmp_path / "tsconfig.json"
    cfg.write_text("{ invalid }")

    with pytest.raises(ValueError):
        load_tsconfig_compiler_options(cfg)

