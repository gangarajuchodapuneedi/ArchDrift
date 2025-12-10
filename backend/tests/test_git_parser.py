"""Basic smoke tests for git_parser module.

These are minimal tests to verify imports and basic function signatures.
For full testing, you would need actual Git repositories or mocks.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

# Import the module to test
from utils.git_parser import clone_or_open_repo, list_commits


def test_imports():
    """Test that the module can be imported without errors."""
    from utils import git_parser

    assert hasattr(git_parser, "clone_or_open_repo")
    assert hasattr(git_parser, "list_commits")


def test_clone_or_open_repo_invalid_url():
    """Test that clone_or_open_repo raises ValueError for empty URL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="repo_url cannot be empty"):
            clone_or_open_repo("", tmpdir)


def test_list_commits_invalid_path():
    """Test that list_commits raises ValueError for non-existent path."""
    with pytest.raises(ValueError, match="Repository path does not exist"):
        list_commits("/nonexistent/path/to/repo")


def test_list_commits_not_a_directory():
    """Test that list_commits raises ValueError for non-directory path."""
    with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
        tmpfile_path = tmpfile.name
        try:
            with pytest.raises(ValueError, match="Repository path is not a directory"):
                list_commits(tmpfile_path)
        finally:
            Path(tmpfile_path).unlink()


# Note: Full integration tests would require:
# - A test Git repository (or mocking GitPython)
# - Testing actual clone operations
# - Testing commit listing with real commits
# These are left as future work for a more complete test suite.

