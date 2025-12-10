"""Drift type detection utilities.

This module analyzes commit messages and file paths to determine the
category/type of architectural drift.

Allowed drift types:
- "architecture": Structural changes, layer violations, design patterns
- "api_contract": API changes, breaking contracts, versioning
- "schema_db": Database schema changes, migrations, data model changes
- "config_env": Configuration, environment variables, deployment config
- "ui_ux": Frontend UI/UX changes, component structure
- "security_policy": Security changes, access control, policies
- "process_governance": Process changes, workflows, governance
- "data_ml": Data pipeline changes, ML model changes
"""


def detect_drift_type(commit_message: str, files_changed: list[str]) -> str:
    """
    Detect the drift type from commit message and changed files.

    Args:
        commit_message: The commit message text.
        files_changed: List of file paths that were changed.

    Returns:
        str: The detected drift type (defaults to "architecture" if unclear).
    """
    message_lower = commit_message.lower()
    files_lower = [f.lower() for f in files_changed]

    # API Contract patterns
    if any(
        keyword in message_lower
        for keyword in [
            "api",
            "endpoint",
            "route",
            "contract",
            "breaking",
            "version",
            "deprecate",
        ]
    ) or any("api/" in f or "routes/" in f or "endpoints/" in f for f in files_lower):
        return "api_contract"

    # Schema/DB patterns
    if any(
        keyword in message_lower
        for keyword in [
            "schema",
            "migration",
            "database",
            "table",
            "model",
            "sql",
            "db",
        ]
    ) or any(
        pattern in f
        for f in files_lower
        for pattern in ["migrations/", "schema/", "models/", ".sql", "database/"]
    ):
        return "schema_db"

    # Config/Environment patterns
    if any(
        keyword in message_lower
        for keyword in [
            "config",
            "environment",
            "env",
            "deploy",
            "docker",
            "kubernetes",
            "infrastructure",
        ]
    ) or any(
        pattern in f
        for f in files_lower
        for pattern in [
            "config/",
            ".env",
            "docker",
            "k8s",
            "infra/",
            ".yaml",
            ".yml",
        ]
    ):
        return "config_env"

    # UI/UX patterns
    if any(
        keyword in message_lower
        for keyword in ["ui", "ux", "component", "frontend", "design", "layout"]
    ) or any(
        pattern in f
        for f in files_lower
        for pattern in [
            "components/",
            "pages/",
            ".jsx",
            ".tsx",
            ".vue",
            "frontend/",
        ]
    ):
        return "ui_ux"

    # Security/Policy patterns
    if any(
        keyword in message_lower
        for keyword in [
            "security",
            "auth",
            "permission",
            "access",
            "policy",
            "authorization",
            "authentication",
        ]
    ) or any("auth/" in f or "security/" in f or "policy/" in f for f in files_lower):
        return "security_policy"

    # Process/Governance patterns
    if any(
        keyword in message_lower
        for keyword in [
            "process",
            "workflow",
            "governance",
            "ci/cd",
            "pipeline",
            "review",
        ]
    ) or any(
        pattern in f
        for f in files_lower
        for pattern in [".github/", "ci/", "workflows/", "pipeline"]
    ):
        return "process_governance"

    # Data/ML patterns
    if any(
        keyword in message_lower
        for keyword in [
            "data",
            "ml",
            "model",
            "pipeline",
            "etl",
            "analytics",
            "training",
        ]
    ) or any(
        pattern in f
        for f in files_lower
        for pattern in ["data/", "ml/", "models/", "pipeline/", "analytics/"]
    ):
        return "data_ml"

    # Default to architecture for structural changes
    return "architecture"

