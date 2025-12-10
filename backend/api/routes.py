"""API route definitions for ArchDrift."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.drift import Drift, DriftListResponse
from services.drift_engine import analyze_repo_for_drifts
from services.drift_store import get_drift_by_id, list_drifts
from utils.git_parser import clone_or_open_repo, list_commits

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
        
        # Run the blocking analysis in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        drifts = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                analyze_repo_for_drifts,
                payload.repo_url,
                base_clone_dir,
                max_commits,
                max_drifts,
            ),
            timeout=300.0  # 5 minute timeout
        )
        
        return drifts
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Analysis timed out. Try reducing max_commits or use a smaller repository."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# TEMPORARY DEBUG ENDPOINTS
# ============================================================================
# These endpoints are for development/testing purposes and may be removed
# or refactored in future versions.


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

