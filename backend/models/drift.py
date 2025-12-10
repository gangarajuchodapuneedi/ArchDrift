"""Data models for architectural drift detection.

Current implementation: Drift model includes id, date, type, title, summary, functionality,
advantage/disadvantage, root_cause, files_changed, commit_hash, repo_url, teams, driftType.
API endpoint /drifts returns DriftListResponse with items array.
Frontend: DriftTimeline component (src/components/DriftTimeline.jsx) renders drifts using 
DriftNode component (src/components/DriftNode.jsx).
"""

from pydantic import BaseModel


class Drift(BaseModel):
    """Represents an architectural drift detected in a codebase."""

    id: str
    date: str  # ISO-8601 datetime
    type: str  # "positive" or "negative"
    title: str
    summary: str
    functionality: str
    advantage: str | None = None
    disadvantage: str | None = None
    root_cause: str | None = None
    files_changed: list[str]
    commit_hash: str
    repo_url: str
    teams: list[str] = []  # Teams/personas responsible for this drift (e.g., ["Backend", "Frontend"])
    driftType: str = "architecture"  # Category of drift: "architecture", "api_contract", "schema_db", "config_env", "ui_ux", "security_policy", "process_governance", "data_ml"
    
    # MMM: Mentor fields
    impactLevel: str = "unknown"  # "high" | "medium" | "low" | "unknown"
    riskAreas: list[str] = []  # e.g. ["Maintainability", "Testability"]
    recommendedActions: list[str] = []  # List of concrete next steps


class DriftListResponse(BaseModel):
    """Response model for listing drifts."""

    items: list[Drift]

