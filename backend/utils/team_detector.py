"""Team detection utilities based on file paths.

This module analyzes file paths to determine which teams/personas are
responsible for changes, based on common directory patterns.
"""


def detect_teams_from_files(files_changed: list[str]) -> list[str]:
    """
    Detect teams/personas responsible for changes based on file paths.

    Args:
        files_changed: List of file paths that were changed.

    Returns:
        list[str]: List of team names (e.g., ["Backend", "Frontend"]).
                  Returns empty list if no patterns match.
    """
    if not files_changed:
        return []

    teams = set()

    for file_path in files_changed:
        file_path_lower = file_path.lower()

        # Frontend patterns
        if any(
            pattern in file_path_lower
            for pattern in [
                "frontend/",
                "src/components/",
                "src/pages/",
                "src/views/",
                "public/",
                "static/",
                ".jsx",
                ".tsx",
                ".vue",
                "components/",
                "pages/",
                "app/",
                "client/",
            ]
        ):
            teams.add("Frontend")

        # Backend patterns
        if any(
            pattern in file_path_lower
            for pattern in [
                "backend/",
                "api/",
                "routes/",
                "controllers/",
                "services/",
                "server/",
                ".py",
                ".go",
                ".java",
                "src/api/",
                "src/routes/",
                "src/controllers/",
            ]
        ):
            teams.add("Backend")

        # Database patterns
        if any(
            pattern in file_path_lower
            for pattern in [
                "models/",
                "db/",
                "database/",
                "migrations/",
                "schema/",
                ".sql",
                "queries/",
                "repositories/",
            ]
        ):
            teams.add("DB")

        # Infrastructure patterns
        if any(
            pattern in file_path_lower
            for pattern in [
                "infra/",
                "infrastructure/",
                "docker",
                "kubernetes",
                "k8s",
                ".yaml",
                ".yml",
                "deploy",
                "ci/",
                ".github/",
                "terraform",
                "ansible",
            ]
        ):
            teams.add("Infrastructure")

        # Shared/Common patterns
        if any(
            pattern in file_path_lower
            for pattern in [
                "shared/",
                "common/",
                "utils/",
                "lib/",
                "types/",
                "interfaces/",
            ]
        ):
            teams.add("Shared")

    # If no teams detected, return ["Unknown"] as fallback
    if not teams:
        return ["Unknown"]

    # Return sorted list for consistency
    return sorted(list(teams))

