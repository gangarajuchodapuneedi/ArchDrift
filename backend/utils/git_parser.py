"""Git repository parsing utilities for ArchDrift.

This module provides functions to clone/open Git repositories and extract
commit metadata for architectural drift analysis.
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from git import Repo, GitCommandError, InvalidGitRepositoryError
from git.cmd import Git


def _ensure_safe_directory(repo_path: str) -> None:
    """
    Ensure Git trusts the repository directory to avoid 'dubious ownership' errors.
    
    This is a security feature in Git that prevents accessing repositories owned
    by different users. We configure Git to trust our .repos directory.
    """
    try:
        git_cmd = Git()
        resolved_path = str(Path(repo_path).resolve())
        # Try to add the directory to safe.directory config (global)
        # Use --replace-all to avoid duplicates if it already exists
        try:
            git_cmd.config("--global", "--replace-all", "safe.directory", resolved_path)
        except Exception:
            # If replace-all fails, try add (might already be set)
            try:
                git_cmd.config("--global", "--add", "safe.directory", resolved_path)
            except Exception:
                # If both fail, try local config
                try:
                    git_cmd = Git(repo_path)
                    git_cmd.config("--local", "--add", "safe.directory", resolved_path)
                except Exception:
                    # If all fail, continue anyway - might work without it
                    pass
    except Exception:
        # If Git command creation fails, continue anyway
        pass


def clone_or_open_repo(repo_url: str, base_clone_dir: str) -> str:
    """
    Clone a Git repository or open an existing clone.

    If the repository is already cloned locally (based on folder name derived
    from repo_url), it will reuse the existing clone. Otherwise, it clones
    the repository into the base_clone_dir.
    """
    if not repo_url or not repo_url.strip():
        raise ValueError("repo_url cannot be empty")

    parsed = urlparse(repo_url)
    repo_name = os.path.basename(parsed.path).replace(".git", "")
    if not repo_name:
        raise ValueError(f"Could not extract repository name from URL: {repo_url}")

    base_path = Path(base_clone_dir).resolve()
    base_path.mkdir(parents=True, exist_ok=True)

    repo_path = base_path / repo_name
    repo_path_str = str(repo_path)

    # If repository already exists, verify it's a valid Git repo and return it
    if repo_path.exists() and repo_path.is_dir():
        try:
            # Ensure Git trusts this directory
            _ensure_safe_directory(repo_path_str)
            Repo(repo_path_str)
            return repo_path_str
        except InvalidGitRepositoryError as e:
            raise InvalidGitRepositoryError(
                f"Directory {repo_path} exists but is not a valid Git repository. "
                "Please remove it or use a different base_clone_dir."
            ) from e

    # Clone the repository
    try:
        Repo.clone_from(repo_url, repo_path_str)
        # Ensure Git trusts the newly cloned directory
        _ensure_safe_directory(repo_path_str)
        return repo_path_str
    except GitCommandError as e:
        # Wrap low-level Git error into a simpler exception
        detail = getattr(e, "stderr", None) or str(e)
        raise RuntimeError(
            f"Failed to clone repository from {repo_url}: {detail}. "
            "Please check the URL and ensure you have network access."
        ) from e
    except Exception as e:
        raise OSError(f"Unexpected error while cloning repository: {str(e)}") from e


def list_commits(
    local_repo_path: str, max_commits: Optional[int] = None
) -> list[dict]:
    """
    List commit metadata from a local Git repository.

    Returns a list of commit dictionaries with keys:
    - hash
    - author
    - email
    - date
    - message
    - files_changed (list of file paths)
    """
    repo_path = Path(local_repo_path).resolve()

    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {local_repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Repository path is not a directory: {local_repo_path}")

    repo_path_str = str(repo_path)
    
    # Ensure Git trusts this directory before opening
    _ensure_safe_directory(repo_path_str)
    
    try:
        repo = Repo(repo_path_str)
    except InvalidGitRepositoryError as e:
        raise InvalidGitRepositoryError(
            f"Path is not a valid Git repository: {local_repo_path}"
        ) from e

    # OPTIMIZATION: Only iterate the commits we need, don't load all into memory
    commit_iter = repo.iter_commits()
    if max_commits is not None and max_commits > 0:
        # Use islice to limit without loading all commits
        from itertools import islice
        commit_iter = islice(commit_iter, max_commits)
    else:
        # Still limit to reasonable default to avoid hanging on huge repos
        from itertools import islice
        commit_iter = islice(commit_iter, 1000)  # Safety limit

    result: list[dict] = []
    for commit in commit_iter:
        # Get changed files for this commit
        files_changed = []
        try:
            # Compare with parent commit to get changed files
            if commit.parents:
                # Has parent - get diff
                parent = commit.parents[0]
                diff = parent.diff(commit)
                for item in diff:
                    # Handle renames, additions, deletions, and modifications
                    path = item.b_path if item.b_path else item.a_path
                    if path:
                        files_changed.append(path)
            else:
                # First commit - get all files in this commit
                for item in commit.tree.traverse():
                    if item.type == "blob":  # File, not directory
                        files_changed.append(item.path)
        except Exception:
            # If we can't get files, continue with empty list
            files_changed = []

        result.append(
            {
                "hash": commit.hexsha,
                "author": commit.author.name,
                "email": commit.author.email,
                "date": commit.committed_datetime.isoformat(),
                "message": commit.message.strip(),
                "files_changed": files_changed,
            }
        )

    return result
