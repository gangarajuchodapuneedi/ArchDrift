"""Tests for Python import dependency extractor.

These tests verify that extract_python_import_modules() correctly extracts
imported module references from Python source code, with proper filtering
based on internal_prefixes.
"""

import pytest

from utils.deps_python import extract_python_import_modules


def test_relative_import_included_no_prefixes():
    """Test that relative import is included when internal_prefixes is None."""
    source = "from . import foo"
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == ["."]


def test_relative_import_with_module():
    """Test that relative import with module name is included."""
    source = "from ..pkg.sub import x"
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == ["..pkg.sub"]


def test_absolute_imports_excluded_no_prefixes():
    """Test that absolute imports are excluded when internal_prefixes is None."""
    source = "import os\nimport myapp.utils\nfrom json import dumps"
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == []


def test_absolute_internal_import_included():
    """Test that absolute internal imports are included when internal_prefixes is set."""
    source = "import myapp.utils\nfrom myapp.core import a"
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    assert result == ["myapp.core", "myapp.utils"]


def test_absolute_external_import_excluded():
    """Test that absolute external imports are excluded even when internal_prefixes is set."""
    source = "import requests\nfrom os import path\nimport myapp.x"
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    assert result == ["myapp.x"]


def test_dedup_and_sorting():
    """Test that duplicate imports are deduplicated and results are sorted."""
    source = """
import myapp.utils
from myapp.core import a
import myapp.utils
from myapp.core import b
import myapp.x
"""
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    assert result == ["myapp.core", "myapp.utils", "myapp.x"]


def test_syntax_error_raises_value_error():
    """Test that SyntaxError raises ValueError with line number."""
    source = "def bad(:\n  pass"
    with pytest.raises(ValueError) as exc_info:
        extract_python_import_modules(source, internal_prefixes=None)
    assert "Syntax error" in str(exc_info.value)
    assert "line" in str(exc_info.value).lower()


def test_multiple_relative_import_levels():
    """Test multiple relative import levels (., .., ...)."""
    source = """
from . import a
from .. import b
from ...pkg import c
from ....module import d
"""
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert "." in result
    assert ".." in result
    assert "...pkg" in result
    assert "....module" in result


def test_mixed_absolute_and_relative_imports():
    """Test mixed absolute and relative imports with internal_prefixes."""
    source = """
import os
from . import local
from ..parent import sibling
import myapp.utils
"""
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    # Relative imports should be included, absolute internal should be included
    assert "." in result
    assert "..parent" in result
    assert "myapp.utils" in result
    # External absolute should be excluded
    assert "os" not in result


def test_import_aliases():
    """Test that import aliases don't affect module extraction."""
    source = """
import myapp.utils as utils
from myapp.core import a as alias_a
"""
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    assert "myapp.utils" in result
    assert "myapp.core" in result
    # Aliases should not appear in results
    assert "utils" not in result
    assert "alias_a" not in result


def test_multiple_imports_in_one_statement():
    """Test multiple imports in a single import statement."""
    source = "import myapp.a, myapp.b, myapp.c"
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    assert result == ["myapp.a", "myapp.b", "myapp.c"]


def test_empty_source_text():
    """Test that empty source text returns empty list."""
    source = ""
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == []


def test_relative_import_no_module():
    """Test relative import with no module part (from . import)."""
    source = "from . import foo, bar"
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == ["."]


def test_relative_import_with_module():
    """Test relative import with module part (from ..pkg import)."""
    source = "from ..pkg import x, y"
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == ["..pkg"]


def test_multiple_internal_prefixes():
    """Test that multiple internal prefixes work correctly."""
    source = """
import myapp.utils
import otherlib.core
import thirdlib.x
"""
    result = extract_python_import_modules(
        source, internal_prefixes={"myapp", "otherlib"}
    )
    assert "myapp.utils" in result
    assert "otherlib.core" in result
    assert "thirdlib.x" not in result


def test_nested_module_imports():
    """Test that nested module imports are handled correctly."""
    source = """
import myapp.utils.helpers
from myapp.core.submodule import func
"""
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    assert "myapp.utils.helpers" in result
    assert "myapp.core.submodule" in result


def test_relative_import_always_included_with_prefixes():
    """Test that relative imports are always included even when internal_prefixes is set."""
    source = """
from . import local
import myapp.utils
"""
    result = extract_python_import_modules(source, internal_prefixes={"myapp"})
    # Relative import should be included
    assert "." in result
    # Internal absolute should be included
    assert "myapp.utils" in result


def test_complex_relative_import():
    """Test complex relative import with multiple levels and module."""
    source = "from ...parent.child import something"
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == ["...parent.child"]


def test_import_from_with_no_module():
    """Test 'from . import' with no module specified."""
    source = "from . import *"
    result = extract_python_import_modules(source, internal_prefixes=None)
    assert result == ["."]

