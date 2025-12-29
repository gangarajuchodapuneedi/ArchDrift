"""Data models for architectural drift detection.

Current implementation: Drift model includes id, date, type, title, summary, functionality,
advantage/disadvantage, root_cause, files_changed, commit_hash, repo_url, teams, driftType.
API endpoint /drifts returns DriftListResponse with items array.
Frontend: DriftTimeline component (src/components/DriftTimeline.jsx) renders drifts using 
DriftNode component (src/components/DriftNode.jsx).
"""

from pydantic import BaseModel, Field


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
    teams: list[str] = Field(default_factory=list)  # Teams/personas responsible for this drift (e.g., ["Backend", "Frontend"])
    driftType: str = "architecture"  # Category of drift: "architecture", "api_contract", "schema_db", "config_env", "ui_ux", "security_policy", "process_governance", "data_ml"
    
    # MMM: Mentor fields
    impactLevel: str = "unknown"  # "high" | "medium" | "low" | "unknown"
    riskAreas: list[str] = Field(default_factory=list)  # e.g. ["Maintainability", "Testability"]
    recommendedActions: list[str] = Field(default_factory=list)  # List of concrete next steps

    # Conformance evidence fields (MT_14, MT_15)
    classification: str | None = None  # "negative" | "positive" | "needs_review" | "unknown" | "no_change"
    edges_added_count: int = 0
    edges_removed_count: int = 0
    forbidden_edges_added_count: int = 0
    forbidden_edges_removed_count: int = 0
    cycles_added_count: int = 0
    cycles_removed_count: int = 0
    baseline_hash: str | None = None
    rules_hash: str | None = None
    reason_codes: list[str] = Field(default_factory=list)  # Always returns [] (never None/missing)
    evidence_preview: list[dict] = Field(default_factory=list)  # Always returns [] (never None/missing)
    classifier_mode_used: str | None = None  # "keywords" | "conformance" | None (for backward compatibility)


class DriftListResponse(BaseModel):
    """Response model for listing drifts."""

    items: list[Drift]

