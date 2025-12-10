"""Drift engine for converting Git commits into architectural drift objects.

This module is responsible for analyzing commits into Drift objects.
All drift textual fields (title, summary, functionality, disadvantage, rootCause, recommendedActions)
must be derived here from commit data (Mirror + Mentor), not in the frontend.

Currently uses simple keyword matching; will be enhanced with AI analysis in future versions.
"""

from pathlib import Path
from typing import Dict, List, Any

from models.drift import Drift
from utils.git_parser import clone_or_open_repo, list_commits
from utils.team_detector import detect_teams_from_files
from utils.drift_type_detector import detect_drift_type


# Keywords that suggest positive architectural changes
POSITIVE_KEYWORDS = [
    "refactor",
    "cleanup",
    "optimize",
    "improve",
    "scale",
    "migrate",
    "restructure",
    "reorganize",
    "abstract",
    "decouple",
]


def summarize_changed_areas(changed_files: List[str]) -> str:
    """Extract top-level directories from changed files to identify impacted areas."""
    roots = []
    for path in changed_files:
        if not path:
            continue
        root = path.split("/", 1)[0]
        if root not in roots:
            roots.append(root)
    if not roots:
        return "core system"
    if len(roots) == 1:
        return roots[0]
    return ", ".join(roots)


def analyze_drift_text(
    commit_message: str,
    changed_files: List[str],
    drift_type: str,
    sentiment: str,
) -> Dict[str, Any]:
    """
    Analyze commit data to generate all textual Mirror/Mentor fields for a drift.
    
    Args:
        commit_message: Full commit message
        changed_files: List of file paths changed in the commit
        drift_type: Category of drift (e.g., "architecture", "api_contract", "schema_db")
        sentiment: "positive" or "negative"
    
    Returns:
        Dictionary with title, summary, functionality, disadvantage, rootCause, recommendedActions
    """
    # Extract commit subject (first line)
    message_lines = commit_message.split("\n")
    subject = message_lines[0].strip() if message_lines else "Untitled commit"
    
    # Title: use commit subject, limit length
    title = subject
    if len(title) > 100:
        title = title[:97] + "..."
    
    # Summary: contextualize based on drift type
    if drift_type == "architecture":
        summary = f"This change introduces an architecture-level drift: {subject}"
    elif drift_type == "api_contract":
        summary = f"This change modifies the API contract: {subject}"
    elif drift_type == "schema_db":
        summary = f"This change affects database schema or structure: {subject}"
    elif drift_type == "config_env":
        summary = f"This change modifies configuration or environment setup: {subject}"
    elif drift_type == "ui_ux":
        summary = f"This change affects user interface or user experience: {subject}"
    elif drift_type == "security_policy":
        summary = f"This change relates to security or policy: {subject}"
    elif drift_type == "process_governance":
        summary = f"This change affects process or governance: {subject}"
    elif drift_type == "data_ml":
        summary = f"This change affects data processing or machine learning: {subject}"
    else:
        summary = f"This change may affect {drift_type or 'system behavior'}: {subject}"
    
    # Functionality: derive from changed file areas
    areas = summarize_changed_areas(changed_files)
    functionality = (
        f"This change impacts functionality in the {areas} area(s), based on the changed files."
    )
    
    # Disadvantage: contextualize based on sentiment and drift type
    disadvantage = None
    if sentiment == "negative":
        if drift_type == "architecture":
            disadvantage = (
                "This drift may increase coupling and make future changes to this area harder."
            )
        elif drift_type == "api_contract":
            disadvantage = (
                "If clients are not updated, this API contract drift may break frontend or integration code."
            )
        elif drift_type == "schema_db":
            disadvantage = (
                "Schema drift can create data inconsistencies or make rollbacks harder."
            )
        elif drift_type == "config_env":
            disadvantage = (
                "Configuration drift can lead to environment-specific issues or deployment failures."
            )
        elif drift_type == "ui_ux":
            disadvantage = (
                "UI/UX drift may create inconsistent user experiences across different parts of the application."
            )
        elif drift_type == "security_policy":
            disadvantage = (
                "Security or policy drift may introduce vulnerabilities or compliance issues."
            )
        else:
            disadvantage = (
                "This drift may introduce additional complexity or maintenance overhead in the impacted area."
            )
    
    # Root cause: explain why drift was detected
    if drift_type == "architecture":
        root_cause = (
            "The drift was detected because the changes in the impacted files do not follow the expected architecture pattern "
            "(for example, routes accessing lower-level components directly)."
        )
    elif drift_type == "api_contract":
        root_cause = (
            "The drift was detected because the API behavior or response shape appears to diverge from the existing contract."
        )
    elif drift_type == "schema_db":
        root_cause = (
            "The drift was detected because database-related files changed in ways that differ from the expected schema or migration patterns."
        )
    elif drift_type == "config_env":
        root_cause = (
            "The drift was detected because configuration or environment files changed in ways that may affect system behavior."
        )
    elif drift_type == "ui_ux":
        root_cause = (
            "The drift was detected because UI/UX-related files changed in ways that may affect user experience consistency."
        )
    elif drift_type == "security_policy":
        root_cause = (
            "The drift was detected because security or policy-related changes may introduce new risks or compliance concerns."
        )
    else:
        root_cause = (
            "The drift was detected based on changes in the impacted files that differ from expected patterns for this area."
        )
    
    # Recommended actions: tailored per drift type
    recommended_actions: List[str] = []
    
    if drift_type == "architecture":
        recommended_actions = [
            "Review the architecture guidelines for this service or module.",
            "Refactor the code to route access through the intended layer (for example, API → Service → DB).",
            "Document the architectural decision or exception in an ADR so the team understands the trade-offs.",
        ]
    elif drift_type == "api_contract":
        recommended_actions = [
            "Review API consumers (frontend or other services) to ensure they are compatible with this change.",
            "Update your API specification or documentation to reflect the new contract.",
            "Add tests to catch regressions if the contract changes unexpectedly.",
        ]
    elif drift_type == "schema_db":
        recommended_actions = [
            "Review database migration scripts to ensure they are reversible and well-tested.",
            "Verify that all environments (dev, staging, production) can handle the schema changes.",
            "Document the schema evolution and any breaking changes for the team.",
        ]
    elif drift_type == "config_env":
        recommended_actions = [
            "Review configuration changes across all environments to ensure consistency.",
            "Document any new configuration requirements or environment-specific settings.",
            "Add validation to catch configuration errors early in the deployment process.",
        ]
    elif drift_type == "ui_ux":
        recommended_actions = [
            "Review UI/UX changes for consistency with design system guidelines.",
            "Ensure user experience remains consistent across different parts of the application.",
            "Document any intentional design deviations and their rationale.",
        ]
    elif drift_type == "security_policy":
        recommended_actions = [
            "Review security implications of the changes and ensure they meet security requirements.",
            "Update security documentation or policies if necessary.",
            "Consider security testing or review by the security team.",
        ]
    else:
        # Generic fallback
        recommended_actions = [
            "Review the change in the context of your system design.",
            "Align the implementation with established patterns where possible.",
            "Document any deliberate deviations from the standard architecture.",
        ]
    
    return {
        "title": title,
        "summary": summary,
        "functionality": functionality,
        "disadvantage": disadvantage,
        "rootCause": root_cause,
        "recommendedActions": recommended_actions,
    }


def commits_to_drifts(repo_url: str, commits: list[dict], max_drifts: int = 5) -> list[Drift]:
    """
    Convert a list of commit dictionaries into Drift objects using simple heuristics.

    Args:
        repo_url: The repository URL.
        commits: List of commit dictionaries from list_commits().
        max_drifts: Maximum number of drifts to generate.

    Returns:
        list[Drift]: List of Drift objects created from commits.
    """
    drifts: list[Drift] = []
    
    # Use at most max_drifts commits (most recent first)
    selected_commits = commits[:max_drifts]
    
    for commit in selected_commits:
        commit_message_full = commit.get("message", "")
        commit_message_lower = commit_message_full.lower()
        commit_hash = commit.get("hash", "")
        commit_date = commit.get("date", "")
        files_changed = commit.get("files_changed", [])
        
        # Detect teams from file paths
        teams = detect_teams_from_files(files_changed)
        
        # Detect drift type category
        drift_type_category = detect_drift_type(commit_message_full, files_changed)
        
        # Determine drift type (positive/negative) based on keywords
        is_positive = any(keyword in commit_message_lower for keyword in POSITIVE_KEYWORDS)
        sentiment = "positive" if is_positive else "negative"
        
        # Analyze drift text from commit data
        text_info = analyze_drift_text(
            commit_message=commit_message_full,
            changed_files=files_changed,
            drift_type=drift_type_category,
            sentiment=sentiment,
        )
        
        # MMM: Mentor - Set default impact and risk areas based on drift type
        if sentiment == "negative":
            impact_level = "high"  # Negative drifts are typically high impact
            risk_areas = ["Maintainability", "Testability"]
        else:  # positive
            impact_level = "medium"
            risk_areas = ["Maintainability"]
        
        # Set advantage for positive drifts
        advantage = None
        if sentiment == "positive":
            advantage = "This change appears to improve the architecture based on commit message keywords."
        
        # Create Drift object with all text fields from analyzer
        drift = Drift(
            id=f"{commit_hash[:8]}",
            date=commit_date,
            type=sentiment,
            title=text_info["title"],
            summary=text_info["summary"],
            functionality=text_info["functionality"],
            advantage=advantage,
            disadvantage=text_info["disadvantage"],
            root_cause=text_info["rootCause"],
            files_changed=files_changed,
            commit_hash=commit_hash,
            repo_url=repo_url,
            teams=teams,
            driftType=drift_type_category,
            impactLevel=impact_level,
            riskAreas=risk_areas,
            recommendedActions=text_info["recommendedActions"],
        )
        
        drifts.append(drift)
    
    return drifts


def analyze_repo_for_drifts(
    repo_url: str,
    base_clone_dir: str,
    max_commits: int = 50,
    max_drifts: int = 5,
) -> list[Drift]:
    """
    Analyze a repository for architectural drifts by examining recent commits.

    This function clones/opens the repository, lists recent commits, and
    converts them into Drift objects using heuristic rules.

    Args:
        repo_url: The Git repository URL to analyze.
        base_clone_dir: Base directory where repositories are stored.
        max_commits: Maximum number of commits to examine.
        max_drifts: Maximum number of drifts to generate.

    Returns:
        list[Drift]: List of detected architectural drifts.

    Raises:
        ValueError: If repo_url is invalid or repository cannot be accessed.
        RuntimeError: If repository cloning fails.
        OSError: If repository path operations fail.
    """
    # Clone or open the repository
    local_repo_path = clone_or_open_repo(repo_url, base_clone_dir)
    
    # List commits
    commits = list_commits(local_repo_path, max_commits=max_commits)
    
    # Convert commits to drifts
    drifts = commits_to_drifts(repo_url, commits, max_drifts=max_drifts)
    
    return drifts

