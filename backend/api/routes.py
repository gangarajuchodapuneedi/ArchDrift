"""API route definitions for ArchDrift."""

import asyncio
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.drift import Drift, DriftListResponse
from services.baseline_service import approve_baseline, generate_baseline, get_baseline_status, baseline_dir_for_repo
from services.drift_engine import analyze_repo_for_drifts, get_drift_classifier_mode, commits_to_drifts, _hash_file
from services.drift_store import get_drift_by_id, list_drifts, set_latest_drifts
from utils.git_parser import clone_or_open_repo, list_commits
from utils.architecture_config import load_architecture_config, _get_default_config_dir
from utils.baseline_store import load_baseline, get_active_exceptions

router = APIRouter()

# Thread pool for CPU-intensive operations
executor = ThreadPoolExecutor(max_workers=2)


@router.get("/health")
async def health_check() -> dict:
    """
    Lightweight endpoint for uptime checks.

    Returns:
        dict: Health status payload.
    """
    return {"status": "healthy"}


# ============================================================================
# DRIFT ENDPOINTS
# ============================================================================


@router.get("/drifts", response_model=DriftListResponse)
async def get_drifts() -> DriftListResponse:
    """
    Retrieve all architectural drifts.

    Returns:
        DriftListResponse: List of all drifts in chronological order.
    """
    drifts = list_drifts()
    return DriftListResponse(items=drifts)


@router.get("/drifts/{drift_id}", response_model=Drift)
async def get_drift(drift_id: str) -> Drift:
    """
    Retrieve a single drift by its ID.

    Args:
        drift_id: The unique identifier of the drift.

    Returns:
        Drift: The drift object.

    Raises:
        HTTPException: 404 if drift not found.
    """
    drift = get_drift_by_id(drift_id)
    if drift is None:
        raise HTTPException(status_code=404, detail="Drift not found")
    return drift


class AnalyzeRepoRequest(BaseModel):
    """Request model for the analyze-repo endpoint."""

    repo_url: str
    max_commits: int | None = 50
    max_drifts: int | None = 5
    classifier_mode: str | None = None  # "keywords" | "conformance" | None (uses env default)


class AnalyzeLocalRepoRequest(BaseModel):
    """Request model for the analyze-local endpoint."""

    repo_path: str
    max_commits: int | None = 50
    max_drifts: int | None = 5
    config_dir: str | None = None
    classifier_mode: str | None = None  # "keywords" | "conformance" | None


@router.post("/analyze-repo", response_model=list[Drift])
async def analyze_repo(payload: AnalyzeRepoRequest) -> list[Drift]:
    """
    Analyze a repository for architectural drifts.

    This is an early heuristic version: it converts recent commits into
    Drift objects using simple keyword-based rules. No AI analysis is
    performed yet.

    Request body:
        {
            "repo_url": "https://github.com/user/repo.git",
            "max_commits": 50,  // optional, defaults to 50
            "max_drifts": 5     // optional, defaults to 5
        }

    Returns:
        list[Drift]: List of detected architectural drifts.

    Raises:
        HTTPException: 400 if repository analysis fails.
    """
    try:
        base_clone_dir = str(Path(__file__).resolve().parent.parent / ".repos")
        max_commits = payload.max_commits or 50
        max_drifts = payload.max_drifts or 5
        
        # Validate classifier_mode if provided
        classifier_mode_override = None
        if payload.classifier_mode is not None:
            if payload.classifier_mode not in ("keywords", "conformance"):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid classifier_mode: {payload.classifier_mode}. Must be 'keywords' or 'conformance'."
                )
            classifier_mode_override = payload.classifier_mode
        
        # Run the blocking analysis in a thread pool to avoid blocking the event loop
        # Use lambda to bind keyword arguments since run_in_executor only accepts positional args
        loop = asyncio.get_event_loop()
        drifts = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: analyze_repo_for_drifts(
                    payload.repo_url,
                    base_clone_dir,
                    max_commits,
                    max_drifts,
                    config_dir=None,
                    data_dir=None,
                    commit_limits=None,
                    classifier_mode_override=classifier_mode_override,
                ),
            ),
            timeout=300.0  # 5 minute timeout
        )
        
        # Store latest drifts for GET /drifts to return
        set_latest_drifts(drifts)
        
        return drifts
    except HTTPException:
        # Re-raise HTTPException to preserve status code (e.g., 422 for validation errors)
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Analysis timed out. Try reducing max_commits or use a smaller repository."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze-local", response_model=list[Drift])
async def analyze_local_repo(payload: AnalyzeLocalRepoRequest) -> list[Drift]:
    """
    Analyze a local repository path for architectural drifts (no cloning).

    This endpoint analyzes a repository that is already on disk, without
    cloning it. Useful for onboarding workflows where the repo is already resolved.

    Request body:
        {
            "repo_path": "C:\\path\\to\\local\\repo",
            "max_commits": 50,  // optional, defaults to 50
            "max_drifts": 5,     // optional, defaults to 5
            "config_dir": "C:\\path\\to\\config",  // optional
            "classifier_mode": "keywords" | "conformance"  // optional
        }

    Returns:
        list[Drift]: List of detected architectural drifts.

    Raises:
        HTTPException: 400 if repository path is invalid or analysis fails.
        HTTPException: 408 if analysis times out.
        HTTPException: 422 if classifier_mode is invalid.
    """
    try:
        # Validate repo_path exists and is a directory
        repo_path_obj = Path(payload.repo_path)
        if not repo_path_obj.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Repository path does not exist: {payload.repo_path}"
            )
        if not repo_path_obj.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Repository path is not a directory: {payload.repo_path}"
            )

        # Validate classifier_mode if provided
        classifier_mode_override = None
        if payload.classifier_mode is not None:
            if payload.classifier_mode not in ("keywords", "conformance"):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid classifier_mode: {payload.classifier_mode}. Must be 'keywords' or 'conformance'."
                )
            classifier_mode_override = payload.classifier_mode

        # Validate config_dir if provided
        if payload.config_dir is not None:
            config_dir_obj = Path(payload.config_dir)
            if not config_dir_obj.exists():
                raise HTTPException(
                    status_code=400,
                    detail=f"config_dir does not exist: {payload.config_dir}"
                )
            if not config_dir_obj.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail=f"config_dir is not a directory: {payload.config_dir}"
                )

        max_commits = payload.max_commits or 50
        max_drifts = payload.max_drifts or 5

        # Run the blocking analysis in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        drifts = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: _analyze_local_repo_worker(
                    str(repo_path_obj),
                    max_commits,
                    max_drifts,
                    payload.config_dir,
                    classifier_mode_override,
                ),
            ),
            timeout=300.0  # 5 minute timeout
        )

        # Store latest drifts for GET /drifts to return
        set_latest_drifts(drifts)

        return drifts
    except HTTPException:
        # Re-raise HTTPException to preserve status code (e.g., 422 for validation errors)
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Analysis timed out. Try reducing max_commits or use a smaller repository."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _analyze_local_repo_worker(
    repo_path: str,
    max_commits: int,
    max_drifts: int,
    config_dir: str | None,
    classifier_mode_override: str | None,
) -> list[Drift]:
    """Worker function to analyze local repo (runs in executor)."""
    # List commits directly (no cloning)
    commits = list_commits(repo_path, max_commits=max_commits)

    # Resolve classifier mode
    from services.drift_engine import resolve_classifier_mode
    resolved_mode = resolve_classifier_mode(classifier_mode_override)

    if resolved_mode != "conformance":
        # Keywords path: call commits_to_drifts directly
        drifts = commits_to_drifts(
            repo_url=f"local:{repo_path}",
            commits=commits,
            max_drifts=max_drifts,
            repo_root_path=repo_path,
            classifier_mode_override=classifier_mode_override,
        )
        return drifts

    # Conformance path: load config and baseline
    try:
        cfg_dir = Path(config_dir) if config_dir else _get_default_config_dir()
        config = load_architecture_config(cfg_dir)
        allowed_rules_path = cfg_dir / "allowed_rules.json"
        rules_hash = _hash_file(allowed_rules_path)
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Conformance: failed to load config/rules: %s", exc)
        rules_hash = None
        config = None

    baseline_data = {
        "baseline_hash": None,
        "baseline_summary": None,
        "baseline_edges_count": None,
        "active_exceptions": [],
    }
    try:
        baseline_dir = baseline_dir_for_repo(Path(repo_path))
        loaded = load_baseline(baseline_dir)
        baseline_data["baseline_hash"] = loaded["summary"].get("baseline_hash_sha256")
        baseline_data["baseline_summary"] = loaded["summary"]
        baseline_data["baseline_edges_count"] = loaded["summary"].get("edge_count")
        baseline_data["active_exceptions"] = get_active_exceptions(baseline_dir)
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Conformance: failed to load baseline: %s", exc)

    from utils.git_commit_graph import Limits as CommitLimits
    drifts = commits_to_drifts(
        repo_url=f"local:{repo_path}",
        commits=commits,
        max_drifts=max_drifts,
        repo_root_path=repo_path,
        commit_limits=CommitLimits(),
        config=config,
        baseline_data=baseline_data,
        rules_hash=rules_hash,
        classifier_mode_override="conformance",
    )

    return drifts


# ============================================================================
# BASELINE ENDPOINTS
# ============================================================================


class GenerateBaselineRequest(BaseModel):
    """Request model for the generate-baseline endpoint."""

    repo_path: str
    config_dir: str | None = None
    max_files: int | None = 2000
    max_file_bytes: int | None = 200_000


@router.post("/baseline/generate")
async def generate_baseline_endpoint(payload: GenerateBaselineRequest) -> dict:
    """
    Generate a baseline snapshot of the current dependency graph for a repository.

    This endpoint loads architecture configuration, builds the dependency graph
    from the repository folder (HEAD working tree), and stores it as a baseline
    with a stable repo_id-based directory structure.

    Request body:
        {
            "repo_path": "/path/to/repo",
            "config_dir": "/path/to/config",  // optional, defaults to backend/architecture
            "max_files": 2000,                // optional, defaults to 2000
            "max_file_bytes": 200000          // optional, defaults to 200000
        }

    Returns:
        dict: Contains baseline_status, baseline_hash_sha256, edge_count, created_at,
              and file processing counts.

    Raises:
        HTTPException: 400 if repository path is invalid or generation fails.
    """
    try:
        repo_root = Path(payload.repo_path)
        if not repo_root.exists():
            raise ValueError(f"Repository path does not exist: {repo_root}")
        if not repo_root.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo_root}")

        config_dir = Path(payload.config_dir) if payload.config_dir else None
        max_files = payload.max_files or 2000
        max_file_bytes = payload.max_file_bytes or 200_000

        # Run the blocking generation in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: generate_baseline(
                    repo_root,
                    config_dir=config_dir,
                    data_dir=None,  # use default
                    max_files=max_files,
                    max_file_bytes=max_file_bytes,
                ),
            ),
            timeout=600.0  # 10 minute timeout
        )

        # Format response with baseline_status and created_at from summary
        status_result = get_baseline_status(repo_root)
        summary = status_result.get("summary", {})

        return {
            "baseline_status": status_result["status"],
            "baseline_hash_sha256": result["baseline_hash_sha256"],
            "edge_count": result["edge_count"],
            "created_at": summary.get("created_at_utc") if summary else None,
            "repo_id": result["repo_id"],
            "baseline_dir": result["baseline_dir"],
            "scanned_files": result["scanned_files"],
            "included_files": result["included_files"],
            "skipped_files": result["skipped_files"],
            "unmapped_files": result["unmapped_files"],
            "unresolved_imports": result["unresolved_imports"],
        }
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Baseline generation timed out. Try reducing max_files or use a smaller repository."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating baseline: {str(e)}"
        )


@router.get("/baseline/status")
async def get_baseline_status_endpoint(repo_path: str) -> dict:
    """
    Get the status of a baseline for a repository (read-only).

    Checks if a baseline exists and returns its status without regenerating it.

    Query parameters:
        repo_path: Path to the repository root directory (required)

    Returns:
        dict: Contains exists (bool), status ("draft" or "missing"),
              baseline_hash_sha256 (if exists), and summary (if exists).

    Raises:
        HTTPException: 400 if repository path is invalid.
    """
    try:
        repo_root = Path(repo_path)
        if not repo_root.exists():
            raise ValueError(f"Repository path does not exist: {repo_root}")
        if not repo_root.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo_root}")

        status_result = get_baseline_status(repo_root)

        return {
            "exists": status_result["exists"],
            "status": status_result["status"],
            "baseline_hash_sha256": status_result["baseline_hash_sha256"],
            "summary": status_result["summary"],
            "approved_by": status_result.get("approved_by"),
            "approved_at": status_result.get("approved_at"),
            "active_exceptions_count": status_result.get("active_exceptions_count", 0),
            "baseline_health": status_result.get("baseline_health", {}),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error checking baseline status: {str(e)}"
        )


class ApproveBaselineRequest(BaseModel):
    """Request model for the approve-baseline endpoint."""

    repo_path: str
    approved_by: str
    approval_note: str | None = None
    exceptions: list[dict] | None = None


@router.post("/baseline/approve")
async def approve_baseline_endpoint(payload: ApproveBaselineRequest) -> dict:
    """
    Approve a baseline and optionally add exceptions.

    This endpoint marks a baseline as accepted and stores approval metadata.
    Optionally, exception rules can be added to allow specific module edges
    temporarily.

    Request body:
        {
            "repo_path": "/path/to/repo",
            "approved_by": "name_or_email",
            "approval_note": "optional note",  // optional
            "exceptions": [  // optional
                {
                    "from_module": "ui",
                    "to_module": "core",
                    "owner": "name_or_email",
                    "reason": "temporary exception",
                    "expires_at": "2024-12-31T23:59:59+00:00"
                }
            ]
        }

    Returns:
        dict: Contains status, approved_by, approved_at, baseline_hash_sha256,
              and active_exceptions_count.

    Raises:
        HTTPException: 400 if repository path is invalid or validation fails.
        HTTPException: 404 if baseline does not exist.
    """
    try:
        repo_root = Path(payload.repo_path)
        if not repo_root.exists():
            raise ValueError(f"Repository path does not exist: {repo_root}")
        if not repo_root.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo_root}")

        # Run the blocking approval in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: approve_baseline(
                    repo_root,
                    approved_by=payload.approved_by,
                    approval_note=payload.approval_note,
                    exceptions=payload.exceptions,
                    data_dir=None,  # use default
                ),
            ),
            timeout=60.0  # 1 minute timeout
        )

        return result
    except ValueError as e:
        error_msg = str(e)
        # Check if it's a missing baseline error
        if "does not exist" in error_msg.lower() or "generate baseline" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error approving baseline: {str(e)}"
        )


# ============================================================================
# ONBOARDING ENDPOINTS
# ============================================================================


class ResolveRepoRequest(BaseModel):
    """Request model for the resolve-repo endpoint."""

    repo_url: str


class SuggestModuleMapRequest(BaseModel):
    """Request model for the suggest-module-map endpoint."""

    repo_path: str
    max_modules: int | None = 8


class ApplyModuleMapRequest(BaseModel):
    """Request model for the apply-module-map endpoint."""

    repo_path: str
    module_map: dict
    config_label: str | None = None


class CreateArchSnapshotRequest(BaseModel):
    """Request model for the architecture-snapshot/create endpoint."""

    repo_path: str
    config_dir: str
    snapshot_label: str | None = None
    created_by: str | None = None
    note: str | None = None


@router.post("/onboarding/resolve-repo")
async def onboarding_resolve_repo(request: ResolveRepoRequest) -> dict:
    """
    Resolve/clone a Git repository and return the local path.

    This endpoint accepts a repository URL, clones it (or reuses existing clone),
    and returns the resolved local path along with the repository name.

    Request body:
        {
            "repo_url": "https://github.com/user/repo.git"
        }

    Returns:
        dict: Contains "repo_url", "repo_path", and "repo_name"

    Raises:
        HTTPException: 400 if repository URL is invalid.
        HTTPException: 408 if repository resolution times out.
        HTTPException: 500 if repository processing fails.
    """
    try:
        # Determine base clone directory (store repos in .repos under backend)
        backend_dir = Path(__file__).parent.parent
        base_clone_dir = backend_dir / ".repos"

        # Run the blocking clone operation in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        repo_path = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: clone_or_open_repo(request.repo_url, str(base_clone_dir)),
            ),
            timeout=300.0  # 5 minute timeout (increased for large repositories)
        )

        # Derive repo_name from the resolved path
        repo_name = Path(repo_path).name

        return {
            "repo_url": request.repo_url,
            "repo_path": repo_path,
            "repo_name": repo_name,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Repository resolution timed out."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing repository: {str(e)}"
        )


def _suggest_module_map_worker(repo_path: str, max_modules: int) -> dict:
    """Worker function to suggest module map (runs in executor)."""
    import re
    from collections import Counter
    
    repo_root = Path(repo_path)
    
    # Check baseline status
    status_result = get_baseline_status(repo_root)
    baseline_health = status_result.get("baseline_health")
    
    # Determine suggestion method
    if isinstance(baseline_health, dict):
        top_unmapped_buckets = baseline_health.get("top_unmapped_buckets", [])
        if isinstance(top_unmapped_buckets, list) and len(top_unmapped_buckets) > 0:
            # Use baseline_health method
            suggestion_method = "baseline_health"
            buckets_data = []
            for bucket_item in top_unmapped_buckets:
                if isinstance(bucket_item, dict) and "bucket" in bucket_item:
                    bucket_name = bucket_item["bucket"]
                    file_count = bucket_item.get("file_count", 0)
                    buckets_data.append({"bucket": bucket_name, "file_count": file_count})
        else:
            suggestion_method = "folder_scan"
            buckets_data = []
    else:
        suggestion_method = "folder_scan"
        buckets_data = []
    
    # If folder_scan, perform scan
    if suggestion_method == "folder_scan":
        allowed_extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rb", ".cs", ".cpp", ".c", ".h", ".hpp"}
        skip_dirs = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", ".cache", "target", "out", "coverage"}
        
        bucket_counts = Counter()
        has_src_dir = (repo_root / "src").exists() and (repo_root / "src").is_dir()
        
        # Walk directory tree
        for file_path in repo_root.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Check extension
            if file_path.suffix.lower() not in allowed_extensions:
                continue
            
            # Check if path contains skip directories
            path_parts = file_path.parts
            if any(skip_dir in path_parts for skip_dir in skip_dirs):
                continue
            
            # Determine bucket
            try:
                relative_path = file_path.relative_to(repo_root)
                parts = relative_path.parts
                
                if len(parts) == 1:
                    # File directly under repo root
                    bucket = "(root)"
                elif has_src_dir and len(parts) >= 2 and parts[0] == "src":
                    # File under src/<X>/...
                    bucket = f"src/{parts[1]}"
                else:
                    # First directory under repo root
                    bucket = parts[0]
                
                bucket_counts[bucket] += 1
            except ValueError:
                # Path not relative to repo_root, skip
                continue
        
        # Convert to list of dicts and sort by count desc
        buckets_data = [{"bucket": bucket, "file_count": count} for bucket, count in bucket_counts.items()]
        buckets_data.sort(key=lambda x: x["file_count"], reverse=True)
    
    # Build notes
    notes = []
    if suggestion_method == "baseline_health":
        notes.append("Derived from baseline_health.top_unmapped_buckets.")
    else:
        notes.append("Derived from folder scan (no baseline health available).")
    
    if len(buckets_data) == 0:
        notes.append("No source files found under scan rules.")
    
    # Limit buckets to top 12 for display
    display_buckets = buckets_data[:12]
    
    # Generate module suggestions
    # Take top N buckets, ignoring "(root)" unless it's the only bucket
    candidate_buckets = [b for b in buckets_data if b["bucket"] != "(root)"]
    if len(candidate_buckets) == 0:
        candidate_buckets = buckets_data  # Use root if it's the only one
    
    selected_buckets = candidate_buckets[:max_modules]
    
    # Check for tests module
    has_tests_at_root = (repo_root / "tests").exists() and (repo_root / "tests").is_dir()
    has_src_tests_bucket = any(b["bucket"] == "src/tests" for b in buckets_data)
    tests_bucket = None
    if has_tests_at_root:
        tests_bucket = "tests"
    elif has_src_tests_bucket:
        tests_bucket = "src/tests"
    
    # Sanitize bucket names to module IDs
    def sanitize_module_id(bucket_name: str) -> str:
        # Convert to lowercase
        sanitized = bucket_name.lower()
        # Replace non-alphanumeric with underscore
        sanitized = re.sub(r'[^a-z0-9]', '_', sanitized)
        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Strip leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized
    
    modules = []
    used_ids = set()
    
    # Add selected buckets as modules
    for bucket_item in selected_buckets:
        bucket_name = bucket_item["bucket"]
        module_id = sanitize_module_id(bucket_name)
        
        # Ensure uniqueness
        original_id = module_id
        counter = 2
        while module_id in used_ids:
            module_id = f"{original_id}_{counter}"
            counter += 1
        
        used_ids.add(module_id)
        modules.append({
            "id": module_id,
            "roots": [bucket_name]
        })
    
    # Add tests module if needed
    if tests_bucket:
        tests_in_selected = any(b["bucket"] == tests_bucket for b in selected_buckets)
        if not tests_in_selected and len(modules) < max_modules + 1:
            module_id = sanitize_module_id(tests_bucket)
            # Ensure uniqueness
            original_id = module_id
            counter = 2
            while module_id in used_ids:
                module_id = f"{original_id}_{counter}"
                counter += 1
            
            used_ids.add(module_id)
            modules.append({
                "id": module_id,
                "roots": [tests_bucket]
            })
    
    # Build module_map_suggestion
    module_map_suggestion = {
        "version": "1.0",
        "unmapped_module_id": "unmapped",
        "modules": modules
    }
    
    # Limit notes to max 5
    notes = notes[:5]
    
    return {
        "repo_path": repo_path,
        "suggestion_method": suggestion_method,
        "buckets": display_buckets,
        "module_map_suggestion": module_map_suggestion,
        "notes": notes
    }


@router.post("/onboarding/suggest-module-map")
async def onboarding_suggest_module_map(payload: SuggestModuleMapRequest) -> dict:
    """
    Suggest a starter module_map.json based on baseline_health or folder scan.

    This endpoint analyzes a repository and suggests a module_map.json structure
    based on either baseline_health.top_unmapped_buckets (if available) or a
    local folder scan.

    Request body:
        {
            "repo_path": "/path/to/repo",
            "max_modules": 8  // optional, defaults to 8
        }

    Returns:
        dict: Contains repo_path, suggestion_method, buckets, module_map_suggestion, and notes

    Raises:
        HTTPException: 400 if repository path is invalid.
        HTTPException: 500 if module map suggestion fails.
    """
    try:
        repo_root = Path(payload.repo_path)
        if not repo_root.exists():
            raise ValueError(f"Repository path does not exist: {repo_root}")
        if not repo_root.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo_root}")
        
        max_modules = payload.max_modules if payload.max_modules is not None else 8
        
        # Run the heavy work in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: _suggest_module_map_worker(str(repo_root), max_modules),
            ),
            timeout=120.0  # 2 minute timeout
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error suggesting module map: {str(e)}"
        )


def _apply_module_map_worker(repo_path: str, module_map: dict, config_label: str | None) -> dict:
    """Worker function to apply module map (runs in executor)."""
    # Validate repo_path
    repo_root = Path(repo_path)
    if not repo_root.exists():
        raise ValueError(f"Invalid repo_path: repository path does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"Invalid repo_path: repository path is not a directory: {repo_root}")
    
    # Validate module_map
    if not isinstance(module_map, dict):
        raise ValueError("module_map must be an object")
    
    # Compute backend_dir
    backend_dir = Path(__file__).parent.parent
    
    # Compute repo_id
    repo_id = hashlib.sha256(str(repo_path).encode("utf-8")).hexdigest()[:12]
    
    # Sanitize config_label
    if config_label:
        label_trimmed = config_label.strip()
        if label_trimmed:
            # Convert to lowercase
            sanitized = label_trimmed.lower()
            # Replace non [a-z0-9_-] with underscore
            sanitized = re.sub(r'[^a-z0-9_-]', '_', sanitized)
            # Collapse consecutive underscores
            sanitized = re.sub(r'_+', '_', sanitized)
            # Strip leading/trailing underscores
            sanitized = sanitized.strip('_')
            label_dir = sanitized if sanitized else "default"
        else:
            label_dir = "default"
    else:
        label_dir = "default"
    
    # Determine config_dir
    base_dir = backend_dir / ".onboarding" / "configs" / repo_id
    config_dir = base_dir / label_dir
    
    # Create config_dir
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Write module_map.json atomically
    module_map_path = config_dir / "module_map.json"
    temp_path = config_dir / "module_map.json.tmp"
    
    # Write JSON to temp file
    json_content = json.dumps(module_map, indent=2, sort_keys=True)
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(json_content)
        f.flush()
        os.fsync(f.fileno())
    
    # Atomically replace temp with final
    os.replace(temp_path, module_map_path)
    
    # Create default allowed_rules.json if it doesn't exist
    allowed_rules_path = config_dir / "allowed_rules.json"
    if not allowed_rules_path.exists():
        allowed_rules_default = {
            "version": "1.0",
            "deny_by_default": True,
            "allowed_edges": []
        }
        with open(allowed_rules_path, "w", encoding="utf-8") as f:
            json.dump(allowed_rules_default, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
    
    # Create default exceptions.json if it doesn't exist
    exceptions_path = config_dir / "exceptions.json"
    if not exceptions_path.exists():
        exceptions_default = {
            "version": "1.0",
            "exceptions": []
        }
        with open(exceptions_path, "w", encoding="utf-8") as f:
            json.dump(exceptions_default, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
    
    # Compute SHA256 of module_map.json file bytes
    with open(module_map_path, "rb") as f:
        file_bytes = f.read()
    module_map_sha256 = hashlib.sha256(file_bytes).hexdigest()
    
    # Build notes
    notes = ["Module map saved server-side (repo not modified)."]
    notes = notes[:5]  # Limit to max 5
    
    return {
        "repo_path": repo_path,
        "repo_id": repo_id,
        "config_dir": str(config_dir.resolve()),
        "module_map_path": str(module_map_path.resolve()),
        "module_map_sha256": module_map_sha256,
        "notes": notes
    }


@router.post("/onboarding/apply-module-map")
async def onboarding_apply_module_map(payload: ApplyModuleMapRequest) -> dict:
    """
    Apply a module_map.json configuration server-side without modifying the repo.

    This endpoint persists a module_map.json file in backend/.onboarding/configs/
    and returns the config_dir path that can be used with baseline endpoints.

    Request body:
        {
            "repo_path": "/path/to/repo",
            "module_map": { ... },
            "config_label": "suggested_v1"  // optional
        }

    Returns:
        dict: Contains repo_path, repo_id, config_dir, module_map_path, module_map_sha256, and notes

    Raises:
        HTTPException: 400 if repository path or module_map is invalid.
        HTTPException: 500 if module map application fails.
    """
    try:
        # Run the file write work in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: _apply_module_map_worker(
                    payload.repo_path,
                    payload.module_map,
                    payload.config_label
                ),
            ),
            timeout=60.0  # 1 minute timeout
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error applying module map: {str(e)}"
        )


def _create_arch_snapshot_worker(
    repo_path: str,
    config_dir: str,
    snapshot_label: str | None,
    created_by: str | None,
    note: str | None,
) -> dict:
    """Worker function to create architecture snapshot (runs in executor)."""
    # Validate repo_path
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        raise ValueError(f"Invalid repo_path: {repo_path_obj}")
    if not repo_path_obj.is_dir():
        raise ValueError(f"Invalid repo_path: {repo_path_obj}")
    
    # Validate config_dir
    config_dir_obj = Path(config_dir)
    if not config_dir_obj.exists():
        raise ValueError(f"Invalid config_dir: {config_dir_obj}")
    if not config_dir_obj.is_dir():
        raise ValueError(f"Invalid config_dir: {config_dir_obj}")
    
    # Validate module_map.json exists
    module_map_path = config_dir_obj / "module_map.json"
    if not module_map_path.exists():
        raise ValueError(f"module_map.json not found in config_dir: {config_dir_obj}")
    
    # Compute backend_dir
    backend_dir = Path(__file__).parent.parent
    
    # Compute repo_id
    repo_id = hashlib.sha256(str(repo_path).encode("utf-8")).hexdigest()[:12]
    
    # Read module_map.json bytes and compute SHA256
    module_map_bytes = module_map_path.read_bytes()
    module_map_sha256 = hashlib.sha256(module_map_bytes).hexdigest()
    
    # Attempt to get rules_hash (best-effort)
    rules_hash = None
    try:
        allowed_rules_path = config_dir_obj / "allowed_rules.json"
        rules_hash = _hash_file(allowed_rules_path)
    except Exception:
        rules_hash = None
    
    # Attempt to get baseline_hash (best-effort)
    baseline_hash = None
    try:
        baseline_dir = baseline_dir_for_repo(repo_path_obj)
        loaded = load_baseline(baseline_dir)
        baseline_hash = loaded["summary"].get("baseline_hash_sha256")
    except Exception:
        baseline_hash = None
    
    # Compute snapshot_id (content-addressed)
    snapshot_input = module_map_sha256 + "|" + (rules_hash or "") + "|" + (baseline_hash or "")
    snapshot_id = hashlib.sha256(snapshot_input.encode("utf-8")).hexdigest()[:16]
    
    # Create snapshot directory
    snapshots_root = backend_dir / ".onboarding" / "snapshots" / repo_id
    snapshot_dir = snapshots_root / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    # Check idempotency
    metadata_path = snapshot_dir / "metadata.json"
    snapshot_module_map_path = snapshot_dir / "module_map.json"
    is_new = not (metadata_path.exists() and snapshot_module_map_path.exists())
    
    # Get created_at_utc timestamp
    created_at_utc = datetime.now(timezone.utc).isoformat()
    
    if is_new:
        # Write module_map.json atomically
        temp_module_map_path = snapshot_dir / "module_map.json.tmp"
        with open(temp_module_map_path, "wb") as f:
            f.write(module_map_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_module_map_path, snapshot_module_map_path)
        
        # Write metadata.json atomically
        metadata_content = {
            "snapshot_id": snapshot_id,
            "repo_id": repo_id,
            "repo_path": repo_path,
            "config_dir": config_dir,
            "module_map_sha256": module_map_sha256,
            "rules_hash": rules_hash,
            "baseline_hash": baseline_hash,
            "snapshot_label": snapshot_label,
            "created_by": created_by,
            "note": note,
            "created_at_utc": created_at_utc,
        }
        metadata_json = json.dumps(metadata_content, indent=2, sort_keys=True)
        temp_metadata_path = snapshot_dir / "metadata.json.tmp"
        with open(temp_metadata_path, "w", encoding="utf-8") as f:
            f.write(metadata_json)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_metadata_path, metadata_path)
        
        # Read created_at_utc from metadata if we just created it
        with open(metadata_path, "r", encoding="utf-8") as f:
            saved_metadata = json.load(f)
            created_at_utc = saved_metadata["created_at_utc"]
    else:
        # Read created_at_utc from existing metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            saved_metadata = json.load(f)
            created_at_utc = saved_metadata["created_at_utc"]
    
    return {
        "repo_path": repo_path,
        "repo_id": repo_id,
        "snapshot_id": snapshot_id,
        "snapshot_dir": str(snapshot_dir.resolve()),
        "module_map_sha256": module_map_sha256,
        "rules_hash": rules_hash,
        "baseline_hash": baseline_hash,
        "created_at_utc": created_at_utc,
        "is_new": is_new,
    }


@router.post("/onboarding/architecture-snapshot/create")
async def onboarding_arch_snapshot_create(payload: CreateArchSnapshotRequest) -> dict:
    """
    Create an immutable architecture snapshot for a repository.
    
    This endpoint creates a content-addressed snapshot of the architecture configuration
    (module_map.json + optional rules/baseline hashes) that can be used to track
    architecture evolution over time.
    
    Request body:
        {
            "repo_path": "/path/to/repo",
            "config_dir": "/path/to/config",
            "snapshot_label": "v1",  // optional
            "created_by": "user@example.com",  // optional
            "note": "Initial snapshot"  // optional
        }
    
    Returns:
        dict: Contains repo_path, repo_id, snapshot_id, snapshot_dir, module_map_sha256,
              rules_hash, baseline_hash, created_at_utc, and is_new
    
    Raises:
        HTTPException: 400 if repository path, config_dir, or module_map.json is invalid.
        HTTPException: 500 if snapshot creation fails.
    """
    try:
        # Run the snapshot creation work in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: _create_arch_snapshot_worker(
                    payload.repo_path,
                    payload.config_dir,
                    payload.snapshot_label,
                    payload.created_by,
                    payload.note,
                ),
            ),
            timeout=60.0  # 1 minute timeout
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating architecture snapshot: {str(e)}"
        )


def _list_arch_snapshots_worker(repo_path: str, limit: int) -> dict:
    """Worker function to list architecture snapshots (runs in executor)."""
    # Validate repo_path
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        raise ValueError(f"Invalid repo_path: {repo_path_obj}")
    if not repo_path_obj.is_dir():
        raise ValueError(f"Invalid repo_path: {repo_path_obj}")
    
    # Validate limit
    if limit < 1 or limit > 100:
        raise ValueError(f"Invalid limit: {limit}. Must be 1..100.")
    
    # Compute backend_dir
    backend_dir = Path(__file__).parent.parent
    
    # Compute repo_id
    repo_id = hashlib.sha256(str(repo_path).encode("utf-8")).hexdigest()[:12]
    
    # Compute snapshots_root
    snapshots_root = backend_dir / ".onboarding" / "snapshots" / repo_id
    
    # If snapshots_root doesn't exist, return empty list
    if not snapshots_root.exists():
        return {
            "repo_path": repo_path,
            "repo_id": repo_id,
            "snapshots": [],
        }
    
    # Collect snapshots
    snapshots = []
    for snapshot_dir in snapshots_root.iterdir():
        # Only process directories
        if not snapshot_dir.is_dir():
            continue
        
        metadata_path = snapshot_dir / "metadata.json"
        if not metadata_path.exists():
            # Skip if metadata.json doesn't exist (don't error)
            continue
        
        try:
            # Load metadata.json
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            # Skip if metadata.json can't be loaded (don't error)
            continue
        
        # Build snapshot entry
        snapshot_entry = {
            "snapshot_id": metadata.get("snapshot_id") or snapshot_dir.name,
            "created_at_utc": metadata.get("created_at_utc") or "",
            "snapshot_label": metadata.get("snapshot_label"),
            "created_by": metadata.get("created_by"),
            "note": metadata.get("note"),
            "module_map_sha256": metadata.get("module_map_sha256"),
            "rules_hash": metadata.get("rules_hash"),
            "baseline_hash": metadata.get("baseline_hash"),
        }
        snapshots.append(snapshot_entry)
    
    # Sort snapshots descending by created_at_utc
    # Treat missing/empty created_at_utc as lowest (appear last)
    def sort_key(snapshot):
        created_at = snapshot.get("created_at_utc") or ""
        # Return tuple: (has_value, value) so empty strings sort last
        return (bool(created_at), created_at)
    
    snapshots.sort(key=sort_key, reverse=True)
    
    # Apply limit
    snapshots = snapshots[:limit]
    
    return {
        "repo_path": repo_path,
        "repo_id": repo_id,
        "snapshots": snapshots,
    }


@router.get("/onboarding/architecture-snapshot/list")
async def onboarding_arch_snapshot_list(repo_path: str, limit: int = 20) -> dict:
    """
    List architecture snapshots for a repository.
    
    This endpoint returns previously created architecture snapshots for a repository,
    sorted by creation date (newest first).
    
    Query parameters:
        repo_path: Path to the repository root directory (required)
        limit: Maximum number of snapshots to return (optional, default 20, range 1-100)
    
    Returns:
        dict: Contains repo_path, repo_id, and snapshots array
    
    Raises:
        HTTPException: 400 if repository path is invalid.
        HTTPException: 422 if limit is out of range.
        HTTPException: 500 if listing fails.
    """
    try:
        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid limit: {limit}. Must be 1..100."
            )
        
        # Run the filesystem scanning work in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: _list_arch_snapshots_worker(repo_path, limit),
            ),
            timeout=30.0  # 30 second timeout
        )
        
        return result
    except HTTPException:
        # Re-raise HTTPException to preserve status code
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing architecture snapshots: {str(e)}"
        )


def _resolve_effective_config_worker(repo_path: str, snapshot_id: str | None) -> dict:
    """Worker function to resolve effective config (runs in executor)."""
    # Validate repo_path
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        raise ValueError(f"Invalid repo_path: repository path does not exist: {repo_path_obj}")
    if not repo_path_obj.is_dir():
        raise ValueError(f"Invalid repo_path: repository path is not a directory: {repo_path_obj}")
    
    # Validate snapshot_id pattern if provided
    if snapshot_id is not None:
        if not re.match(r'^[a-f0-9]{16}$', snapshot_id):
            raise ValueError(f"Invalid snapshot_id: {snapshot_id}. Must be 16 lowercase hex chars.")
    
    # Compute backend_dir
    backend_dir = Path(__file__).parent.parent
    
    # Compute repo_id
    repo_id = hashlib.sha256(str(repo_path).encode("utf-8")).hexdigest()[:12]
    
    # Compute snapshots_root
    snapshots_root = backend_dir / ".onboarding" / "snapshots" / repo_id
    
    # If snapshots_root doesn't exist, raise error
    if not snapshots_root.exists():
        raise ValueError("No snapshots found for repo.")
    
    # Resolve snapshot directory
    if snapshot_id is not None:
        snapshot_dir = snapshots_root / snapshot_id
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        if not snapshot_dir.is_dir():
            raise ValueError(f"Snapshot not found: {snapshot_id}")
    else:
        # Find latest snapshot by reading metadata.json
        candidates = []
        for child_dir in snapshots_root.iterdir():
            if not child_dir.is_dir():
                continue
            metadata_path = child_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                created_at_utc = metadata.get("created_at_utc", "")
                if created_at_utc:
                    candidates.append((created_at_utc, child_dir))
            except Exception:
                # Skip if metadata.json can't be loaded
                continue
        
        if not candidates:
            raise ValueError("No valid snapshot metadata found.")
        
        # Sort by created_at_utc descending (ISO-8601 string compare)
        candidates.sort(key=lambda x: x[0], reverse=True)
        snapshot_dir = candidates[0][1]
        snapshot_id = snapshot_dir.name
    
    # Validate module_map.json exists
    module_map_path = snapshot_dir / "module_map.json"
    if not module_map_path.exists():
        raise ValueError("Snapshot is missing module_map.json")
    
    # Read module_map.json bytes and compute SHA256
    module_map_bytes = module_map_path.read_bytes()
    module_map_sha256 = hashlib.sha256(module_map_bytes).hexdigest()
    
    # Read metadata.json if exists, else {}
    metadata_path = snapshot_dir / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            metadata = {}
    else:
        metadata = {}
    
    # Return exact keys only
    return {
        "repo_path": repo_path,
        "repo_id": repo_id,
        "snapshot_id": snapshot_id,
        "config_dir": str(snapshot_dir.resolve()),
        "module_map_path": str(module_map_path.resolve()),
        "module_map_sha256": module_map_sha256,
        "created_at_utc": metadata.get("created_at_utc", ""),
        "snapshot_label": metadata.get("snapshot_label"),
        "created_by": metadata.get("created_by"),
        "note": metadata.get("note"),
    }


@router.get("/onboarding/effective-config")
async def onboarding_effective_config(
    repo_path: str,
    snapshot_id: str | None = None
) -> dict:
    """
    Resolve the effective config_dir (snapshot directory) for a repository.
    
    This endpoint resolves which snapshot configuration to use for conformance analysis.
    If snapshot_id is provided, it uses that specific snapshot. Otherwise, it selects
    the latest snapshot by created_at_utc.
    
    Query parameters:
        repo_path: Path to the repository root directory (required)
        snapshot_id: Optional snapshot ID (16 lowercase hex chars) to use specific snapshot
    
    Returns:
        dict: Contains repo_path, repo_id, snapshot_id, config_dir, module_map_path,
              module_map_sha256, created_at_utc, snapshot_label, created_by, and note
    
    Raises:
        HTTPException: 400 if repository path is invalid or snapshot not found.
        HTTPException: 404 if no snapshots found for repo or snapshot not found.
        HTTPException: 422 if snapshot_id format is invalid.
        HTTPException: 500 if resolution fails.
    """
    try:
        # Validate repo_path exists and is directory
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repo_path: {repo_path_obj}"
            )
        if not repo_path_obj.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repo_path: {repo_path_obj}"
            )
        
        # Validate snapshot_id pattern if provided
        if snapshot_id is not None:
            if not re.match(r'^[a-f0-9]{16}$', snapshot_id):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid snapshot_id: {snapshot_id}. Must be 16 lowercase hex chars."
                )
        
        # Run the filesystem work in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                lambda: _resolve_effective_config_worker(repo_path, snapshot_id),
            ),
            timeout=30.0  # 30 second timeout
        )
        
        return result
    except HTTPException:
        # Re-raise HTTPException to preserve status code
        raise
    except ValueError as e:
        error_msg = str(e)
        # Check if it's a "not found" error
        if "not found" in error_msg.lower() or "no snapshots" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error resolving effective config: {str(e)}"
        )


# ============================================================================
# TEMPORARY DEBUG ENDPOINTS
# ============================================================================
# These endpoints are for development/testing purposes and may be removed
# or refactored in future versions.


@router.get("/debug/mode")
async def debug_mode() -> dict:
    """
    Debug endpoint to expose what mode the server is running in.
    
    Returns:
        dict: Contains resolved_mode, env_DRIFT_CLASSIFIER_MODE, pid, and ppid.
    """
    resolved_mode = get_drift_classifier_mode()
    env_value = os.getenv("DRIFT_CLASSIFIER_MODE")
    
    # Get ppid (parent process ID) - available on Unix, not on Windows
    try:
        ppid = os.getppid()
    except AttributeError:
        ppid = None
    
    return {
        "resolved_mode": resolved_mode,
        "env_DRIFT_CLASSIFIER_MODE": env_value if env_value is not None else None,
        "pid": os.getpid(),
        "ppid": ppid,
    }


class ListCommitsRequest(BaseModel):
    """Request model for the list-commits debug endpoint."""

    repo_url: str
    max_commits: Optional[int] = None


@router.post("/debug/list-commits")
async def debug_list_commits(request: ListCommitsRequest) -> dict:
    """
    TEMPORARY DEBUG ENDPOINT: Clone/open a Git repository and list commits.

    This endpoint is for testing the Git parser functionality. It accepts a
    repository URL, clones it (or reuses existing clone), and returns commit
    metadata.

    Request body:
        {
            "repo_url": "https://github.com/user/repo.git",
            "max_commits": 20  // optional, defaults to all commits
        }

    Returns:
        dict: Contains "repo_path" and "commits" (list of commit dicts)

    Raises:
        HTTPException: If repository cloning or parsing fails
    """
    try:
        # Determine base clone directory (store repos in .repos under backend)
        backend_dir = Path(__file__).parent.parent
        base_clone_dir = backend_dir / ".repos"

        # Clone or open the repository
        repo_path = clone_or_open_repo(request.repo_url, str(base_clone_dir))

        # List commits
        commits = list_commits(repo_path, max_commits=request.max_commits)

        return {
            "repo_path": repo_path,
            "commit_count": len(commits),
            "commits": commits,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing repository: {str(e)}"
        )

