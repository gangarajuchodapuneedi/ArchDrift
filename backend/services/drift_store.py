"""In-memory store for architectural drifts.

This is a temporary in-memory implementation. In production, this would
be replaced with a database-backed store.
"""

from models.drift import Drift

# In-memory storage for drifts
_DRIFTS: list[Drift] = [
    Drift(
        id="drift-001",
        date="2024-01-15T10:30:00",
        type="negative",
        title="Database layer dependency introduced in API routes",
        summary="API route handlers now directly import database models, violating the layered architecture pattern.",
        functionality="API endpoints now bypass the service layer and access database models directly.",
        advantage=None,
        disadvantage="Tight coupling between API and database layers makes testing and maintenance harder.",
        root_cause="Developer shortcut to avoid creating service layer methods.",
        files_changed=[
            "api/routes.py",
            "api/users.py",
            "models/user.py",
        ],
        commit_hash="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
        repo_url="https://github.com/example/archdrift-demo",
        teams=["Backend", "DB"],
        driftType="architecture",
        impactLevel="high",
        riskAreas=["Maintainability", "Testability"],
        recommendedActions=[
            "Extract database access into a dedicated service layer function.",
            "Update architecture guidelines/ADR to reinforce 'API → Service → DB' rule.",
            "Add regression tests to cover API behaviour via the service layer.",
        ],
        classification=None,
        edges_added_count=0,
        edges_removed_count=0,
        forbidden_edges_added_count=0,
        forbidden_edges_removed_count=0,
        cycles_added_count=0,
        cycles_removed_count=0,
        baseline_hash=None,
        rules_hash=None,
        reason_codes=[],
        evidence_preview=[],
    ),
    Drift(
        id="drift-002",
        date="2024-01-20T14:15:00",
        type="positive",
        title="Service layer abstraction introduced",
        summary="New service layer created to properly separate business logic from API routes.",
        functionality="API routes now delegate to service classes, improving separation of concerns.",
        advantage="Better testability, maintainability, and adherence to clean architecture principles.",
        disadvantage=None,
        root_cause="Refactoring effort to improve code organization.",
        files_changed=[
            "services/user_service.py",
            "services/order_service.py",
            "api/routes.py",
        ],
        commit_hash="b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1",
        repo_url="https://github.com/example/archdrift-demo",
        teams=["Backend"],
        driftType="architecture",
        impactLevel="medium",
        riskAreas=["Maintainability"],
        recommendedActions=[
            "Ensure new routes use the service layer instead of accessing DB directly.",
            "Document the new abstraction in architecture docs/ADR.",
        ],
        classification=None,
        edges_added_count=0,
        edges_removed_count=0,
        forbidden_edges_added_count=0,
        forbidden_edges_removed_count=0,
        cycles_added_count=0,
        cycles_removed_count=0,
        baseline_hash=None,
        rules_hash=None,
        reason_codes=[],
        evidence_preview=[],
    ),
    Drift(
        id="drift-003",
        date="2024-01-25T09:45:00",
        type="negative",
        title="Circular dependency between modules",
        summary="Module A imports Module B, which imports Module C, which imports Module A, creating a circular dependency.",
        functionality="Application still works but module loading order is fragile.",
        advantage=None,
        disadvantage="Makes code harder to understand and can cause import errors in certain scenarios.",
        root_cause="Lack of clear module boundaries and dependency direction.",
        files_changed=[
            "modules/module_a.py",
            "modules/module_b.py",
            "modules/module_c.py",
        ],
        commit_hash="c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2",
        repo_url="https://github.com/example/archdrift-demo",
        teams=["Backend"],
        driftType="architecture",
        impactLevel="high",
        riskAreas=["Maintainability", "Complexity"],
        recommendedActions=[
            "Refactor modules to remove circular imports (introduce a shared lower-level module if needed).",
            "Add an architecture rule to prevent circular dependencies in future.",
        ],
        classification=None,
        edges_added_count=0,
        edges_removed_count=0,
        forbidden_edges_added_count=0,
        forbidden_edges_removed_count=0,
        cycles_added_count=0,
        cycles_removed_count=0,
        baseline_hash=None,
        rules_hash=None,
        reason_codes=[],
        evidence_preview=[],
    ),
    Drift(
        id="drift-004",
        date="2024-02-01T16:20:00",
        type="positive",
        title="Dependency injection pattern implemented",
        summary="Services now use dependency injection, making components more testable and loosely coupled.",
        functionality="Dependencies are injected rather than hard-coded, enabling better unit testing.",
        advantage="Improved testability, flexibility, and adherence to SOLID principles.",
        disadvantage=None,
        root_cause="Refactoring to improve code quality and test coverage.",
        files_changed=[
            "services/base_service.py",
            "services/user_service.py",
            "api/routes.py",
            "config/dependencies.py",
        ],
        commit_hash="d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3",
        repo_url="https://github.com/example/archdrift-demo",
        teams=["Backend"],
        driftType="architecture",
        impactLevel="medium",
        riskAreas=["Testability"],
        recommendedActions=[
            "Adopt DI for new services and routes to keep dependencies explicit.",
            "Add unit tests that inject test doubles for key collaborators.",
        ],
        classification=None,
        edges_added_count=0,
        edges_removed_count=0,
        forbidden_edges_added_count=0,
        forbidden_edges_removed_count=0,
        cycles_added_count=0,
        cycles_removed_count=0,
        baseline_hash=None,
        rules_hash=None,
        reason_codes=[],
        evidence_preview=[],
    ),
]

# In-memory storage for latest drifts from analyze-repo
# This is updated by POST /analyze-repo and returned by GET /drifts if present
_LATEST_DRIFTS: list[Drift] | None = None


def set_latest_drifts(drifts: list[Drift]) -> None:
    """
    Store the latest drifts from analyze-repo.

    Args:
        drifts: List of Drift objects from the most recent analysis.
    """
    global _LATEST_DRIFTS
    _LATEST_DRIFTS = drifts


def get_latest_drifts() -> list[Drift] | None:
    """
    Get the latest drifts from analyze-repo, if any.

    Returns:
        list[Drift] | None: Latest drifts if available, None otherwise.
    """
    return _LATEST_DRIFTS


def list_drifts() -> list[Drift]:
    """
    Return all drifts in chronological order (oldest first).

    Returns latest_drifts if present (from analyze-repo), otherwise returns demo drifts.

    Returns:
        list[Drift]: List of all drifts sorted by date (ascending).
    """
    # Return latest drifts if available, else fall back to demo drifts
    if _LATEST_DRIFTS is not None:
        return sorted(_LATEST_DRIFTS, key=lambda d: d.date)
    return sorted(_DRIFTS, key=lambda d: d.date)


def get_drift_by_id(drift_id: str) -> Drift | None:
    """
    Retrieve a single drift by its ID.

    Args:
        drift_id: The unique identifier of the drift.

    Returns:
        Drift | None: The drift if found, None otherwise.
    """
    # Search latest drifts first, then fall back to demo drifts
    if _LATEST_DRIFTS is not None:
        for drift in _LATEST_DRIFTS:
            if drift.id == drift_id:
                return drift
    for drift in _DRIFTS:
        if drift.id == drift_id:
            return drift
    return None

