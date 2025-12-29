"""Drift engine for converting Git commits into architectural drift objects.

This module is responsible for analyzing commits into Drift objects.
All drift textual fields (title, summary, functionality, disadvantage, rootCause, recommendedActions)
must be derived here from commit data (Mirror + Mentor), not in the frontend.

Currently uses simple keyword matching; will be enhanced with AI analysis in future versions.
"""

import hashlib
import os
import logging
from pathlib import Path
from typing import Dict, List, Any

from models.drift import Drift
from utils.git_parser import clone_or_open_repo, list_commits
from utils.team_detector import detect_teams_from_files
from utils.drift_type_detector import detect_drift_type
from utils.architecture_config import load_architecture_config, _get_default_config_dir
from utils.conformance_compare import compare_edges
from utils.rule_checker import check_rules
from utils.drift_classifier import classify_drift, assess_conformance_readiness
from utils.git_commit_graph import build_commit_delta, Limits as CommitLimits
from utils.dependency_graph import build_dependency_graph  # imported for test monkeypatches
from services.baseline_service import baseline_dir_for_repo
from utils.baseline_store import load_baseline, get_active_exceptions

logger = logging.getLogger(__name__)


def _hash_file(path: Path) -> str | None:
    """Compute SHA-256 hash of a file; return None if missing or unreadable."""
    if not path.exists() or not path.is_file():
        return None
    try:
        data = path.read_bytes()
    except Exception:
        return None
    return hashlib.sha256(data).hexdigest()


def _run_conformance_pipeline(repo_root: Path) -> dict:
    """Run conformance analysis for the current repo HEAD (architecture only).
    
    Returns a dictionary with classification, reason_codes, summary counts,
    baseline_hash, and rules_hash. Handles missing baseline/rules gracefully.
    """
    result = {
        "classification": "unknown",
        "reason_codes": ["missing_baseline"],
        "summary": {
            "edges_added_count": 0,
            "edges_removed_count": 0,
            "forbidden_edges_added_count": 0,
            "forbidden_edges_removed_count": 0,
            "cycles_added_count": 0,
            "cycles_removed_count": 0,
        },
        "baseline_hash": None,
        "rules_hash": None,
    }

    # Load architecture config and compute rules hash
    try:
        config_dir = _get_default_config_dir()
        config = load_architecture_config(config_dir)
        allowed_rules_path = config_dir / "allowed_rules.json"
        rules_hash = _hash_file(allowed_rules_path)
        result["rules_hash"] = rules_hash
    except Exception as exc:
        logger.warning("Conformance: failed to load architecture config: %s", exc)
        result["reason_codes"] = ["missing_rules"]
        return result

    # Load baseline (prefer accepted if available)
    baseline_dir = baseline_dir_for_repo(repo_root)
    try:
        baseline_loaded = load_baseline(baseline_dir)
        baseline_edges = baseline_loaded["edges"]
        baseline_hash = baseline_loaded["summary"].get("baseline_hash_sha256")
        result["baseline_hash"] = baseline_hash
        result["reason_codes"] = []
    except Exception as exc:
        logger.warning("Conformance: failed to load baseline: %s", exc)
        result["reason_codes"] = ["missing_baseline"]
        return result

    # Build current dependency graph
    try:
        current_graph = build_dependency_graph(repo_root, config)
        current_edges = current_graph.get("edges", [])
    except Exception as exc:
        logger.warning("Conformance: dependency graph build failed: %s", exc)
        result["reason_codes"] = ["compare_failed"]
        return result

    # Compare baseline vs current
    try:
        compare_result = compare_edges(baseline_edges, current_edges)
    except Exception as exc:
        logger.warning("Conformance: compare failed: %s", exc)
        result["reason_codes"] = ["compare_failed"]
        return result

    # Get active exceptions and check rules
    try:
        active_exceptions = get_active_exceptions(baseline_dir)
        rules_result = check_rules(compare_result, config, active_exceptions)
    except Exception as exc:
        logger.warning("Conformance: rule check failed: %s", exc)
        result["reason_codes"] = ["compare_failed"]
        return result

    # Detect and diff cycles
    try:
        cycles_result = diff_cycles(
            old_edges=baseline_edges,
            new_edges=current_edges,
        )
    except Exception as exc:
        logger.warning("Conformance: cycle detection failed: %s", exc)
        result["reason_codes"] = ["compare_failed"]
        return result

    # Classify drift
    try:
        analysis = {
            "compare": compare_result,
            "rules": rules_result,
            "cycles": cycles_result,
        }
        classification_result = classify_drift(analysis)
        result["classification"] = classification_result.get("classification", "unknown")
        result["reason_codes"] = classification_result.get("reason_codes", [])
        summary = classification_result.get("summary", {})
        result["summary"] = {
            "edges_added_count": summary.get("edges_added_count", 0),
            "edges_removed_count": summary.get("edges_removed_count", 0),
            "forbidden_edges_added_count": summary.get("forbidden_edges_added_count", 0),
            "forbidden_edges_removed_count": summary.get("forbidden_edges_removed_count", 0),
            "cycles_added_count": summary.get("cycles_added_count", 0),
            "cycles_removed_count": summary.get("cycles_removed_count", 0),
        }
    except Exception as exc:
        logger.warning("Conformance: classification failed: %s", exc)
        result["reason_codes"] = ["compare_failed"]
        return result

    return result


def get_drift_classifier_mode() -> str:
    """Get drift classifier mode from environment variable.
    
    Returns:
        "keywords" or "conformance". Defaults to "keywords" if unset or invalid.
    """
    raw = os.getenv("DRIFT_CLASSIFIER_MODE", "keywords").strip().lower()
    if raw in ("keywords",):
        return "keywords"
    if raw in ("conformance",):
        return "conformance"
    if raw == "":
        return "keywords"
    else:
        logger.warning(
            f"Invalid DRIFT_CLASSIFIER_MODE value '{raw}'. Falling back to 'keywords'."
        )
        return "keywords"


def resolve_classifier_mode(override: str | None) -> str:
    """Resolve classifier mode from override or environment variable.
    
    Args:
        override: Optional override value ("keywords" or "conformance").
        
    Returns:
        "keywords" or "conformance". Uses override if valid, otherwise falls back to env.
    """
    if override in ("keywords", "conformance"):
        return override
    return get_drift_classifier_mode()


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


def _normalize_classifier_mode_used(drift: Drift, requested_mode: str) -> None:
    """
    Normalize classifier_mode_used based on whether conformance was actually applied.
    
    When requested_mode == "conformance", only drifts that actually have conformance
    evidence should have classifier_mode_used="conformance". Others should use "keywords"
    so the UI uses drift.type instead of drift.classification.
    
    Conformance is considered "applied" if ANY of:
    - drift.classification is not None
    - drift.reason_codes exists and len>0
    - drift.baseline_hash is not None or drift.rules_hash is not None
    - any of forbidden_edges_*_count or cycles_*_count is > 0
    
    Args:
        drift: Drift object to normalize (modified in-place)
        requested_mode: The classifier mode requested in the API call
    """
    if requested_mode != "conformance":
        # Not conformance mode, keep as-is
        return
    
    # Check if conformance was actually applied to this drift
    conformance_applied = (
        drift.classification is not None
        or (drift.reason_codes and len(drift.reason_codes) > 0)
        or drift.baseline_hash is not None
        or drift.rules_hash is not None
        or drift.forbidden_edges_added_count > 0
        or drift.forbidden_edges_removed_count > 0
        or drift.cycles_added_count > 0
        or drift.cycles_removed_count > 0
    )
    
    if conformance_applied:
        drift.classifier_mode_used = "conformance"
    else:
        drift.classifier_mode_used = "keywords"


def commits_to_drifts(
    repo_url: str,
    commits: list[dict],
    max_drifts: int = 5,
    repo_root_path: str | None = None,
    commit_limits: CommitLimits | None = None,
    config: Any | None = None,
    baseline_data: dict | None = None,
    rules_hash: str | None = None,
    classifier_mode_override: str | None = None,
) -> list[Drift]:
    """
    Convert a list of commit dictionaries into Drift objects using simple heuristics.

    Args:
        repo_url: The repository URL.
        commits: List of commit dictionaries from list_commits().
        max_drifts: Maximum number of drifts to generate.
        repo_root_path: Optional path to repository root (required for conformance mode).
        classifier_mode_override: Optional override for classifier mode ("keywords" | "conformance").
            If None, uses environment variable.

    Returns:
        list[Drift]: List of Drift objects created from commits.
    """
    # Resolve classifier mode from override or environment
    resolved_mode = resolve_classifier_mode(classifier_mode_override)
    if commit_limits is None:
        commit_limits = CommitLimits()
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
        
        # Determine drift type (positive/negative) based on classifier mode
        classification = None
        reason_codes: list[str] = []
        conformance_summary: dict = {}
        conformance_result: dict = {}
        evidence_preview: list[dict] = []
        graph_stats: dict = {}
        text_info_override = None
        
        if resolved_mode == "conformance" and drift_type_category == "architecture":
            prereq_missing = not (repo_root_path and config and baseline_data)
            baseline_summary = baseline_data.get("baseline_summary") if baseline_data else None
            baseline_edges_count = baseline_data.get("baseline_edges_count") if baseline_data else None

            if prereq_missing:
                classification = "unknown"
                reason_codes = sorted(set(reason_codes + ["BASELINE_MISSING"]))
                sentiment = "unknown"
                text_info_override = {
                    "title": commit_message_full[:100],
                    "summary": "Conformance classification is Unknown because the baseline is not ready. Generate + approve a baseline and ensure module mapping covers source paths.",
                    "functionality": "",
                    "disadvantage": None,
                    "rootCause": None,
                    "recommendedActions": [
                        "Generate and approve a baseline.",
                        "Ensure module_map.json covers source paths.",
                        "Re-run analysis in conformance mode.",
                    ],
                }
            else:
                # Early readiness check before doing heavy work
                is_ready_initial, readiness_reasons_initial = assess_conformance_readiness(
                    baseline_summary=baseline_summary,
                    baseline_edges_count=baseline_edges_count,
                    graph_stats=None,
                )
                if not is_ready_initial:
                    classification = "unknown"
                    reason_codes = sorted(set(reason_codes + readiness_reasons_initial))
                    sentiment = "unknown"
                    text_info_override = {
                        "title": commit_message_full[:100],
                        "summary": "Conformance classification is Unknown because the baseline is not ready. Generate + approve a baseline and ensure module mapping covers source paths.",
                        "functionality": "",
                        "disadvantage": None,
                        "rootCause": None,
                        "recommendedActions": [
                            "Generate and approve a baseline.",
                            "Ensure module_map.json covers source paths.",
                            "Re-run analysis in conformance mode.",
                        ],
                    }
                else:
                    # Per-commit delta via MT_17
                    try:
                        commit_delta = build_commit_delta(
                            repo_path=repo_root_path,
                            commit_sha=commit_hash,
                            config=config,
                            limits=commit_limits,
                        )
                    except Exception as exc:
                        logger.warning("Conformance commit delta failed for %s: %s", commit_hash, exc)
                        commit_delta = {
                            "edges_added": [],
                            "edges_removed": [],
                            "edges_added_count": 0,
                            "edges_removed_count": 0,
                            "evidence": [],
                            "truncated": False,
                            "stats": {},
                        }
                        reason_codes = ["compare_failed"]
                        classification = "unknown"
                        conformance_summary = {
                            "edges_added_count": 0,
                            "edges_removed_count": 0,
                            "forbidden_edges_added_count": 0,
                            "forbidden_edges_removed_count": 0,
                            "cycles_added_count": 0,
                            "cycles_removed_count": 0,
                        }
                    else:
                        # Build a compare-like structure from delta
                        compare_like = {
                            "edges_added": commit_delta.get("edges_added", []),
                            "edges_removed": commit_delta.get("edges_removed", []),
                            "counts": {
                                "divergence": commit_delta.get("edges_added_count", 0),
                                "absence": commit_delta.get("edges_removed_count", 0),
                                "edges_added_count": commit_delta.get("edges_added_count", 0),
                                "edges_removed_count": commit_delta.get("edges_removed_count", 0),
                            },
                        }
                        # Rule check
                        rules_result = check_rules(compare_like, config, baseline_data.get("active_exceptions", []))
                        # Cycles: per MT_18 safe rule, keep zero
                        cycles_result = {
                            "counts": {"cycles_added_count": 0, "cycles_removed_count": 0},
                            "cycles_added": [],
                            "cycles_removed": [],
                        }
                        # Classify
                        analysis = {
                            "compare": compare_like,
                            "rules": rules_result,
                            "cycles": cycles_result,
                        }
                        classification_result = classify_drift(analysis)
                        classification = classification_result.get("classification", "unknown")
                        reason_codes = classification_result.get("reason_codes", [])
                        summary = classification_result.get("summary", {})
                        conformance_summary = {
                            "edges_added_count": commit_delta.get("edges_added_count", 0),
                            "edges_removed_count": commit_delta.get("edges_removed_count", 0),
                            "forbidden_edges_added_count": rules_result.get("counts", {}).get("forbidden_added", 0),
                            "forbidden_edges_removed_count": rules_result.get("counts", {}).get("forbidden_removed", 0),
                            "cycles_added_count": 0,
                            "cycles_removed_count": 0,
                        }
                        graph_stats = commit_delta.get("stats", {})
                        # Build evidence_preview from forbidden edges/cycles matched against commit_delta evidence
                        # Falls back to edge/cycle data itself if evidence matching fails
                        evidence_preview = []
                        forbidden_edges_added_count = rules_result.get("counts", {}).get("forbidden_added", 0)
                        forbidden_edges_removed_count = rules_result.get("counts", {}).get("forbidden_removed", 0)
                        cycles_added_count = cycles_result.get("counts", {}).get("cycles_added_count", 0)
                        cycles_removed_count = cycles_result.get("counts", {}).get("cycles_removed_count", 0)
                        
                        # Get all evidence from commit_delta for matching
                        all_evidence = commit_delta.get("evidence", [])
                        evidence_by_edge = {}
                        for ev in all_evidence:
                            from_mod = ev.get("from_module", "")
                            to_mod = ev.get("to_module", "")
                            if from_mod and to_mod:
                                edge_key = (from_mod, to_mod)
                                if edge_key not in evidence_by_edge:
                                    evidence_by_edge[edge_key] = []
                                evidence_by_edge[edge_key].append(ev)
                        
                        # Handle forbidden edges added
                        if forbidden_edges_added_count > 0:
                            forbidden_edges_added = rules_result.get("forbidden_edges_added", [])
                            for edge in forbidden_edges_added:
                                from_mod = edge.get("from", "")
                                to_mod = edge.get("to", "")
                                if not from_mod or not to_mod:
                                    continue
                                edge_key = (from_mod, to_mod)
                                
                                # Try to match against evidence
                                matched_ev = None
                                if edge_key in evidence_by_edge and evidence_by_edge[edge_key]:
                                    matched_ev = evidence_by_edge[edge_key][0]  # Take first match
                                
                                # Build evidence item (use matched evidence if available, else fallback to edge data)
                                import_ref = ""
                                src_file = ""
                                if matched_ev:
                                    import_ref = matched_ev.get("import_ref", matched_ev.get("import_text", ""))
                                    src_file = matched_ev.get("src_file", matched_ev.get("from_file", ""))
                                else:
                                    # Fallback: create minimal evidence from edge data
                                    src_file = f"{from_mod} → {to_mod}"
                                    import_ref = f"forbidden dependency: {from_mod} → {to_mod}"
                                
                                evidence_preview.append({
                                    "rule": "forbidden_edge_added",
                                    "from_module": from_mod,
                                    "to_module": to_mod,
                                    "src_file": src_file,
                                    "to_file": matched_ev.get("to_file", "") if matched_ev else "",
                                    "import_ref": import_ref,
                                    "import_text": import_ref,  # Frontend expects import_text
                                    "direction": "added",  # Frontend expects direction field
                                })
                        
                        # Handle forbidden edges removed
                        if forbidden_edges_removed_count > 0:
                            forbidden_edges_removed = rules_result.get("forbidden_edges_removed", [])
                            for edge in forbidden_edges_removed:
                                from_mod = edge.get("from", "")
                                to_mod = edge.get("to", "")
                                if not from_mod or not to_mod:
                                    continue
                                edge_key = (from_mod, to_mod)
                                
                                # Try to match against evidence
                                matched_ev = None
                                if edge_key in evidence_by_edge and evidence_by_edge[edge_key]:
                                    matched_ev = evidence_by_edge[edge_key][0]
                                
                                import_ref = ""
                                src_file = ""
                                if matched_ev:
                                    import_ref = matched_ev.get("import_ref", matched_ev.get("import_text", ""))
                                    src_file = matched_ev.get("src_file", matched_ev.get("from_file", ""))
                                else:
                                    src_file = f"{from_mod} → {to_mod}"
                                    import_ref = f"forbidden dependency removed: {from_mod} → {to_mod}"
                                
                                evidence_preview.append({
                                    "rule": "forbidden_edge_removed",
                                    "from_module": from_mod,
                                    "to_module": to_mod,
                                    "src_file": src_file,
                                    "to_file": matched_ev.get("to_file", "") if matched_ev else "",
                                    "import_ref": import_ref,
                                    "import_text": import_ref,
                                    "direction": "removed",  # Frontend expects direction field
                                })
                        
                        # Handle cycles added
                        if cycles_added_count > 0:
                            cycles_added = cycles_result.get("cycles_added", [])
                            for cycle in cycles_added:
                                if not cycle or len(cycle) < 2:
                                    continue
                                # Format cycle as module path
                                cycle_path = " → ".join(cycle)
                                if len(cycle) > 1:
                                    cycle_path += f" → {cycle[0]}"  # Close the cycle
                                
                                evidence_preview.append({
                                    "rule": "cycle_added",
                                    "from_module": cycle[0] if cycle else "",
                                    "to_module": cycle[1] if len(cycle) > 1 else "",
                                    "src_file": f"Cycle: {cycle_path}",
                                    "to_file": "",
                                    "import_ref": f"dependency cycle detected: {cycle_path}",
                                    "import_text": f"dependency cycle detected: {cycle_path}",
                                    "direction": "added",  # Frontend expects direction field
                                })
                        
                        # Handle cycles removed
                        if cycles_removed_count > 0:
                            cycles_removed = cycles_result.get("cycles_removed", [])
                            for cycle in cycles_removed:
                                if not cycle or len(cycle) < 2:
                                    continue
                                cycle_path = " → ".join(cycle)
                                if len(cycle) > 1:
                                    cycle_path += f" → {cycle[0]}"
                                
                                evidence_preview.append({
                                    "rule": "cycle_removed",
                                    "from_module": cycle[0] if cycle else "",
                                    "to_module": cycle[1] if len(cycle) > 1 else "",
                                    "src_file": f"Cycle removed: {cycle_path}",
                                    "to_file": "",
                                    "import_ref": f"dependency cycle removed: {cycle_path}",
                                    "import_text": f"dependency cycle removed: {cycle_path}",
                                    "direction": "removed",  # Frontend expects direction field
                                })
                        
                        # Sort deterministically and take top 10
                        evidence_preview = sorted(
                            evidence_preview,
                            key=lambda e: (
                                e.get("rule", ""),
                                e.get("from_module", ""),
                                e.get("to_module", ""),
                                e.get("src_file", ""),
                                e.get("import_ref", ""),
                            ),
                        )[:10]

            # Readiness guardrail
            is_ready, readiness_reasons = assess_conformance_readiness(
                baseline_summary=baseline_summary,
                baseline_edges_count=baseline_edges_count,
                graph_stats=graph_stats,
            )

            if not is_ready:
                classification = "unknown"
                reason_codes = sorted(set(reason_codes + readiness_reasons))
                sentiment = "unknown"
                # Force neutral text to avoid keyword references (applied after text_info is built)
                text_info_override = {
                    "title": commit_message_full[:100],
                    "summary": "Conformance classification is Unknown because the baseline is not ready. Generate + approve a baseline and ensure module mapping covers source paths.",
                    "functionality": "",
                    "disadvantage": None,
                    "rootCause": None,
                    "recommendedActions": [
                        "Generate and approve a baseline.",
                        "Ensure module_map.json covers source paths.",
                        "Re-run analysis in conformance mode.",
                    ],
                }
            else:
                # Map classification to sentiment for consistency
                if classification == "positive":
                    sentiment = "positive"
                elif classification == "negative":
                    sentiment = "negative"
                elif classification in ("needs_review", "unknown", "no_change"):
                    sentiment = "negative"
                else:
                    sentiment = "negative"
        else:
            # Keywords mode or non-architecture drift: use keyword-based sentiment
            is_positive = any(keyword in commit_message_lower for keyword in POSITIVE_KEYWORDS)
            sentiment = "positive" if is_positive else "negative"
        
        # Analyze drift text from commit data (initialize)
        text_info = analyze_drift_text(
            commit_message=commit_message_full,
            changed_files=files_changed,
            drift_type=drift_type_category,
            sentiment=sentiment,
        )
        # Apply override if conformance not ready
        if text_info_override:
            text_info = {**text_info, **text_info_override}
        
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
        bd_safe = baseline_data or {}
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
            classification=classification,
            edges_added_count=conformance_summary.get("edges_added_count", 0) if classification else 0,
            edges_removed_count=conformance_summary.get("edges_removed_count", 0) if classification else 0,
            forbidden_edges_added_count=conformance_summary.get("forbidden_edges_added_count", 0) if classification else 0,
            forbidden_edges_removed_count=conformance_summary.get("forbidden_edges_removed_count", 0) if classification else 0,
            cycles_added_count=conformance_summary.get("cycles_added_count", 0) if classification else 0,
            cycles_removed_count=conformance_summary.get("cycles_removed_count", 0) if classification else 0,
            baseline_hash=bd_safe.get("baseline_hash") if classification else None,
            rules_hash=rules_hash if classification else None,
            reason_codes=reason_codes if classification else [],
            evidence_preview=evidence_preview if classification else [],
            classifier_mode_used=resolved_mode,
        )
        
        drifts.append(drift)
    
    # Normalize classifier_mode_used: only drifts with actual conformance evidence
    # should have classifier_mode_used="conformance". Others should use "keywords"
    # so UI uses drift.type instead of drift.classification.
    for drift in drifts:
        _normalize_classifier_mode_used(drift, resolved_mode)
    
    return drifts


def analyze_repo_for_drifts(
    repo_url: str,
    base_clone_dir: str,
    max_commits: int = 50,
    max_drifts: int = 5,
    *,
    config_dir: str | None = None,
    data_dir: str | None = None,
    commit_limits: CommitLimits | None = None,
    classifier_mode_override: str | None = None,
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

    # Resolve classifier mode from override or environment
    resolved_mode = resolve_classifier_mode(classifier_mode_override)

    if resolved_mode != "conformance":
        # Keywords path unchanged
        drifts = commits_to_drifts(
            repo_url,
            commits,
            max_drifts=max_drifts,
            repo_root_path=local_repo_path,
            classifier_mode_override=classifier_mode_override,
        )
        return drifts

    # Conformance: load baseline and rules once
    try:
        cfg_dir = Path(config_dir) if config_dir else _get_default_config_dir()
        config = load_architecture_config(cfg_dir)
        allowed_rules_path = cfg_dir / "allowed_rules.json"
        rules_hash = _hash_file(allowed_rules_path)
    except Exception as exc:
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
        baseline_dir = baseline_dir_for_repo(Path(local_repo_path), data_dir=Path(data_dir) if data_dir else None)
        loaded = load_baseline(baseline_dir)
        baseline_data["baseline_hash"] = loaded["summary"].get("baseline_hash_sha256")
        baseline_data["baseline_summary"] = loaded["summary"]
        baseline_data["baseline_edges_count"] = loaded["summary"].get("edge_count")
        baseline_data["active_exceptions"] = get_active_exceptions(baseline_dir)
    except Exception as exc:
        logger.warning("Conformance: failed to load baseline: %s", exc)

    drifts = commits_to_drifts(
        repo_url,
        commits,
        max_drifts=max_drifts,
        repo_root_path=local_repo_path,
        commit_limits=commit_limits or CommitLimits(),
        config=config,
        baseline_data=baseline_data,
        rules_hash=rules_hash,
        classifier_mode_override=classifier_mode_override,
    )

    return drifts

