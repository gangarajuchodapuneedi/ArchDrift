"""Conformance-based drift classifier.

This module provides a deterministic drift classifier that uses ONLY conformance
evidence (edges/rules/cycles) to classify drift, never reading commit message keywords.
"""


def classify_drift(analysis: dict) -> dict:
    """Classify drift based on conformance analysis results.

    Uses compare results, rule checker results, and cycle diff results to
    deterministically classify drift as negative, positive, needs_review, unknown, or no_change.

    Args:
        analysis: Dictionary containing:
            - compare: Output from compare_edges() (MT_11)
            - rules: Output from check_rules() (MT_12)
            - cycles: Output from diff_cycles() (MT_13)

    Returns:
        Dictionary containing:
        - classification: "negative" | "positive" | "needs_review" | "unknown" | "no_change"
        - reason_codes: Sorted list of reason code strings
        - summary: Dictionary with all count fields
    """
    compare = analysis.get("compare")
    rules = analysis.get("rules")
    cycles = analysis.get("cycles")

    # Check for errors/missing data
    reason_codes = []
    if compare is None:
        reason_codes.append("missing_compare")
    if rules is None:
        reason_codes.append("missing_rules")
    elif rules.get("error") is not None:
        reason_codes.append("missing_rules")
    if cycles is None:
        reason_codes.append("missing_cycles")

    if reason_codes:
        # Unknown classification due to missing data
        return {
            "classification": "unknown",
            "reason_codes": sorted(reason_codes),
            "summary": {
                "edges_added_count": 0,
                "edges_removed_count": 0,
                "forbidden_edges_added_count": 0,
                "forbidden_edges_removed_count": 0,
                "cycles_added_count": 0,
                "cycles_removed_count": 0,
            },
        }

    # Extract counts with fallbacks
    compare_counts = compare.get("counts", {})
    edges_added_count = compare_counts.get(
        "divergence", len(compare.get("edges_added", []))
    )
    edges_removed_count = compare_counts.get(
        "absence", len(compare.get("edges_removed", []))
    )

    rules_counts = rules.get("counts", {})
    forbidden_edges_added_count = rules_counts.get(
        "forbidden_added", len(rules.get("forbidden_edges_added", []))
    )
    forbidden_edges_removed_count = rules_counts.get(
        "forbidden_removed", len(rules.get("forbidden_edges_removed", []))
    )

    cycles_counts = cycles.get("counts", {})
    cycles_added_count = cycles_counts.get(
        "cycles_added_count", len(cycles.get("cycles_added", []))
    )
    cycles_removed_count = cycles_counts.get(
        "cycles_removed_count", len(cycles.get("cycles_removed", []))
    )

    # Build summary
    summary = {
        "edges_added_count": edges_added_count,
        "edges_removed_count": edges_removed_count,
        "forbidden_edges_added_count": forbidden_edges_added_count,
        "forbidden_edges_removed_count": forbidden_edges_removed_count,
        "cycles_added_count": cycles_added_count,
        "cycles_removed_count": cycles_removed_count,
    }

    # Apply classification rules
    EA = edges_added_count
    ER = edges_removed_count
    FA = forbidden_edges_added_count
    FR = forbidden_edges_removed_count
    CA = cycles_added_count
    CR = cycles_removed_count

    # 1. Check for no change
    if EA == 0 and ER == 0 and CA == 0 and CR == 0:
        return {
            "classification": "no_change",
            "reason_codes": [],
            "summary": summary,
        }

    # 2. Check for negative (risk-first: forbidden edges added OR cycles added)
    if FA > 0 or CA > 0:
        reason_codes = []
        if FA > 0:
            reason_codes.append("forbidden_edges_added")
        if CA > 0:
            reason_codes.append("cycles_added")
        return {
            "classification": "negative",
            "reason_codes": sorted(reason_codes),
            "summary": summary,
        }

    # 3. Check for positive (forbidden edges removed OR cycles removed, and no negative)
    if FR > 0 or CR > 0:
        reason_codes = []
        if FR > 0:
            reason_codes.append("forbidden_edges_removed")
        if CR > 0:
            reason_codes.append("cycles_removed")
        return {
            "classification": "positive",
            "reason_codes": sorted(reason_codes),
            "summary": summary,
        }

    # 4. Otherwise: needs_review (only allowed edges changed)
    return {
        "classification": "needs_review",
        "reason_codes": ["allowed_edges_changed"],
        "summary": summary,
    }


def assess_conformance_readiness(
    *,
    baseline_summary: dict | None,
    baseline_edges_count: int | None,
    graph_stats: dict | None,
) -> tuple[bool, list[str]]:
    """
    Determine whether conformance classification is ready.

    Returns (is_ready, reason_codes). If not ready, reason_codes contains one or more of:
    - "BASELINE_MISSING"
    - "BASELINE_EMPTY"
    - "NO_SOURCE_FILES"
    - "MAPPING_TOO_LOW"
    """
    reasons: list[str] = []

    # Baseline presence
    if baseline_summary is None or baseline_edges_count is None:
        reasons.append("BASELINE_MISSING")
    else:
        edge_count = baseline_edges_count
        if edge_count == 0:
            reasons.append("BASELINE_EMPTY")

    included = graph_stats.get("included_files") if graph_stats else None
    unmapped = graph_stats.get("unmapped_files") if graph_stats else None

    if included == 0:
        reasons.append("NO_SOURCE_FILES")
    elif included and unmapped is not None:
        try:
            ratio = unmapped / included if included > 0 else 0
            if ratio >= 0.5:
                reasons.append("MAPPING_TOO_LOW")
        except Exception:
            # If stats are malformed, do not add mapping reason
            pass

    is_ready = len(reasons) == 0
    return is_ready, reasons
