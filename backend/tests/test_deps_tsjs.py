"""Tests for JavaScript/TypeScript import dependency extractor.

These tests verify that extract_tsjs_import_specifiers() correctly extracts
import specifiers from JS/TS source code, with proper comment stripping and
filtering based on internal_prefixes.
"""

import pytest

from utils.deps_tsjs import extract_tsjs_import_specifiers


def test_relative_esm_import():
    """Test that relative ESM import is extracted."""
    source = 'import x from "./a";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./a"]


def test_bare_import():
    """Test that bare import statement is extracted."""
    source = 'import "./polyfills";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./polyfills"]


def test_require_relative():
    """Test that relative require() is extracted."""
    source = 'const x = require("../b");'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["../b"]


def test_dynamic_import():
    """Test that dynamic import() is extracted."""
    source = 'async function f(){ await import("./c"); }'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./c"]


def test_export_from():
    """Test that export-from statement is extracted."""
    source = 'export {x} from "./d";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./d"]


def test_absolute_imports_excluded_no_prefixes():
    """Test that absolute imports are excluded when internal_prefixes is None."""
    source = 'import React from "react"; import {x} from "myapp/core";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == []


def test_absolute_internal_included():
    """Test that absolute internal imports are included when internal_prefixes is set."""
    source = 'import {x} from "myapp/core"; import React from "react";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes={"myapp"})
    assert result == ["myapp/core"]


def test_scoped_absolute_internal_included():
    """Test that scoped absolute internal imports are included."""
    source = 'import {Btn} from "@acme/ui/button"; import z from "@other/pkg";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes={"@acme/ui"})
    assert result == ["@acme/ui/button"]


def test_ignore_commented_imports():
    """Test that commented-out imports are ignored."""
    source = '// import x from "./nope"\n/* require("./nope2") */\nimport y from "./yes";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./yes"]


def test_dedup_and_sorting():
    """Test that duplicate specifiers are deduplicated and results are sorted."""
    source = """
import {x} from "./a";
import y from "./a";
const z = require("./a");
export {w} from "./b";
import "./a";
"""
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./a", "./b"]


def test_mixed_relative_and_absolute():
    """Test mixed relative and absolute imports with internal_prefixes."""
    source = """
import React from "react";
import {x} from "./local";
import {y} from "myapp/utils";
"""
    result = extract_tsjs_import_specifiers(source, internal_prefixes={"myapp"})
    assert "./local" in result
    assert "myapp/utils" in result
    assert "react" not in result


def test_multiple_imports_in_statement():
    """Test multiple imports in a single import statement."""
    source = 'import {a, b, c} from "./module";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./module"]


def test_template_strings_in_comments():
    """Test that template strings in comments don't break parsing."""
    source = '// This has `template` strings\nimport x from "./a";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./a"]


def test_string_literals_containing_comment_markers():
    """Test that comment markers inside strings don't break parsing."""
    source = 'const msg = "// not a comment"; import x from "./a";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./a"]


def test_empty_source_text():
    """Test that empty source text returns empty list."""
    source = ""
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == []


def test_scoped_packages_different_prefixes():
    """Test that scoped packages with different prefixes are handled correctly."""
    source = """
import {x} from "@acme/ui/button";
import {y} from "@other/pkg";
"""
    result = extract_tsjs_import_specifiers(source, internal_prefixes={"@acme/ui"})
    assert result == ["@acme/ui/button"]
    assert "@other/pkg" not in result


def test_relative_always_included_with_prefixes():
    """Test that relative imports are always included even when internal_prefixes is set."""
    source = """
from . import local;
import myapp.utils;
"""
    # Note: "from . import" is Python syntax, not JS/TS
    # Let's use valid JS/TS syntax
    source = """
import {x} from "./local";
import {y} from "myapp/utils";
"""
    result = extract_tsjs_import_specifiers(source, internal_prefixes={"myapp"})
    assert "./local" in result
    assert "myapp/utils" in result


def test_block_comment_multiline():
    """Test that multiline block comments are stripped correctly."""
    source = """
/* This is a
   multiline comment
   with import "./fake" */
import x from "./real";
"""
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./real"]


def test_single_quote_imports():
    """Test that single-quoted imports are extracted."""
    source = "import x from './a'; const y = require('../b');"
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert "./a" in result
    assert "../b" in result


def test_export_star_from():
    """Test export * from statement."""
    source = 'export * from "./module";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./module"]


def test_export_named_from():
    """Test export with named exports from statement."""
    source = 'export {a, b as c} from "./module";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./module"]


def test_dynamic_import_with_await():
    """Test dynamic import with await in different contexts."""
    source = """
async function load() {
    const mod = await import("./module");
    return mod;
}
"""
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./module"]


def test_require_with_spaces():
    """Test require() with various spacing."""
    source = 'const x = require( "./a" ); const y = require("./b");'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert "./a" in result
    assert "./b" in result


def test_import_type_statement():
    """Test TypeScript import type statement (should still extract specifier)."""
    source = 'import type {X} from "./types";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./types"]


def test_complex_relative_paths():
    """Test complex relative paths."""
    source = """
import x from "../../../parent";
import y from "./sibling";
import z from "../parent/sibling";
"""
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert "../../../parent" in result
    assert "./sibling" in result
    assert "../parent/sibling" in result


def test_string_escape_sequences():
    """Test that string escape sequences don't break comment stripping."""
    source = 'const s = "string with \\"quotes\\""; import x from "./a";'
    result = extract_tsjs_import_specifiers(source, internal_prefixes=None)
    assert result == ["./a"]

