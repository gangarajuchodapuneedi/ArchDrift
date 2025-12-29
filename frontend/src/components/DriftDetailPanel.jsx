// Renders the MMM: Mirror + Mentor detail for a drift (what happened + what should I do next)
// Multiplier: Copy as ticket button allows exporting drift info as a formatted issue body
import { useState } from "react";
import { getClassificationMeta } from "./classificationUtils";

function DriftDetailPanel({ drift, baselineStatus }) {
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDriftType = (driftType) => {
    const typeMap = {
      architecture: "Architecture",
      api_contract: "API Contract",
      schema_db: "Schema / DB",
      config_env: "Config / Environment",
      ui_ux: "UI / UX",
      security_policy: "Security / Policy",
      process_governance: "Process / Governance",
      data_ml: "Data / ML",
    };
    return typeMap[driftType] || driftType?.charAt(0).toUpperCase() + driftType?.slice(1).replace(/_/g, " ") || "";
  };

  const formatImpactLabel = (level) => {
    switch (level) {
      case "high":
        return "High";
      case "medium":
        return "Medium";
      case "low":
        return "Low";
      default:
        return "Unknown";
    }
  };

  // Multiplier: Build drift ticket body for copy-as-ticket functionality
  const buildDriftTicketBody = (drift, formattedDate, classificationLabel) => {
    const lines = [];
    const driftImpactLevel = drift.impactLevel ?? "unknown";
    const driftRiskAreas = drift.riskAreas ?? [];
    const driftRecommendedActions = drift.recommendedActions ?? [];

    lines.push(`# ${drift.title || "Architecture Drift"}`);
    lines.push("");
    lines.push("## Mirror — What happened");
    lines.push(`- Date: ${formattedDate}`);
    lines.push(`- Classification: ${classificationLabel}`);
    if (drift.driftType) {
      lines.push(`- Type: ${formatDriftType(drift.driftType)}`);
    }
    if (drift.teams && drift.teams.length > 0) {
      lines.push(`- Teams: ${drift.teams.join(", ")}`);
    }
    lines.push("");
    if (drift.summary) {
      lines.push("### Summary");
      lines.push(drift.summary);
      lines.push("");
    }
    if (drift.functionality) {
      lines.push("### Functionality");
      lines.push(drift.functionality);
      lines.push("");
    }
    if (drift.disadvantage) {
      lines.push("### Disadvantage");
      lines.push(drift.disadvantage);
      lines.push("");
    }
    if (drift.root_cause) {
      lines.push("### Root Cause");
      lines.push(drift.root_cause);
      lines.push("");
    }
    if (drift.files_changed && drift.files_changed.length > 0) {
      lines.push("### Files Changed");
      drift.files_changed.forEach((f) => lines.push(`- ${f}`));
      lines.push("");
    }
    if (drift.commit_hash) {
      lines.push(`- Commit: ${drift.commit_hash}`);
    }
    if (drift.repo_url) {
      lines.push(`- Repository: ${drift.repo_url}`);
    }
    lines.push("");

    lines.push("## Mentor — Recommended actions");
    lines.push(`- Impact: ${formatImpactLabel(driftImpactLevel)}`);
    if (driftRiskAreas.length > 0) {
      lines.push(`- Affects: ${driftRiskAreas.join(", ")}`);
    }
    if (driftRecommendedActions.length > 0) {
      lines.push("");
      driftRecommendedActions.forEach((a) => lines.push(`- ${a}`));
    }

    lines.push("");
    return lines.join("\n");
  };

  if (!drift) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-slate-400 text-center">
          Select a drift from the timeline to see details.
        </p>
      </div>
    );
  }

  const classificationInfo = getClassificationMeta(drift);
  const isPositive = classificationInfo.tone === "positive";
  const isNeutral = classificationInfo.tone === "neutral";
  const impactLevel = drift.impactLevel ?? "unknown";
  const riskAreas = drift.riskAreas ?? [];
  const recommendedActions = drift.recommendedActions ?? [];
  const formattedDate = formatDate(drift.date);
  const reasonCodes = drift.reason_codes ?? drift.reasonCodes ?? [];
  const evidence = drift.evidence_preview ?? drift.evidence ?? [];
  const baselineReasonCodes = ["BASELINE_MISSING", "BASELINE_EMPTY", "MAPPING_TOO_LOW", "NO_SOURCE_FILES"];
  const reasonHasBaselineIssue = reasonCodes.some((r) => baselineReasonCodes.includes(r));
  const baselineHealth = baselineStatus?.baseline_health;
  const baselineNotReady =
    !!baselineHealth && (baselineHealth.baseline_ready === false || baselineHealth.mapping_ready === false);
  const unknownWithReason = classificationInfo.key === "unknown" && reasonHasBaselineIssue;
  const showBaselineBanner = baselineNotReady || reasonHasBaselineIssue || unknownWithReason;

  const nextActions =
    (baselineHealth?.next_actions || []).slice(0, 3).filter(Boolean).length > 0
      ? (baselineHealth?.next_actions || []).slice(0, 3).filter(Boolean)
      : [
          "Update module_map.json so files map to modules (src/, packages/, apps/).",
          "POST /baseline/generate then POST /baseline/approve.",
          "Re-run Analyze Repo in conformance mode.",
        ];

  const [copyStatus, setCopyStatus] = useState("");

  async function handleCopyTicket() {
    try {
      const body = buildDriftTicketBody(drift, formattedDate, classificationInfo.label);
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(body);
      } else {
        // Fallback: create a temporary textarea
        const textarea = document.createElement("textarea");
        textarea.value = body;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopyStatus("copied");
      setTimeout(() => setCopyStatus(""), 2000);
    } catch (e) {
      console.error("Failed to copy ticket body", e);
      setCopyStatus("error");
      setTimeout(() => setCopyStatus(""), 3000);
    }
  }

  const advantageText = (() => {
    const raw = drift.advantage || "";
    const lower = raw.toLowerCase();
    const containsKeyword =
      lower.includes("keyword") || lower.includes("commit message");
    if (containsKeyword) {
      return "Classification is based on architecture conformance evidence (edges/rules/cycles), not commit messages.";
    }
    return raw;
  })();

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
      {showBaselineBanner && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-3 text-amber-100">
          <div className="text-sm font-semibold">Baseline not ready</div>
          <p className="text-sm text-amber-50/90 mt-1">
            Conformance needs a real baseline + rules to compare. Generate + approve a baseline, then re-run analysis.
          </p>
          <ul className="list-disc list-inside text-sm text-amber-50/90 mt-2 space-y-1">
            {nextActions.slice(0, 3).map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Header */}
      <div className="border-b border-slate-800 pb-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-2xl font-bold text-slate-100">{drift.title}</h2>
          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 text-sm font-semibold rounded ${
                isPositive
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : isNeutral
                  ? "bg-amber-500/20 text-amber-200 border border-amber-500/40"
                  : "bg-rose-500/20 text-rose-300 border border-rose-500/40"
              }`}
            >
              {classificationInfo.label}
            </span>
            {/* Multiplier: Copy as ticket button */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="px-3 py-1 text-xs rounded-full border border-white/20 bg-white/[0.04] hover:bg-white/[0.08] hover:border-white/35 transition-all cursor-pointer text-slate-300"
                onClick={handleCopyTicket}
              >
                Copy as ticket
              </button>
              {copyStatus === "copied" && (
                <span className="text-xs opacity-80 text-slate-300">Copied!</span>
              )}
              {copyStatus === "error" && (
                <span className="text-xs opacity-80 text-red-400">Copy failed</span>
              )}
            </div>
          </div>
        </div>
        <p className="text-sm text-slate-400">{formattedDate}</p>
        
        {/* MMM: MENTOR — Impact badge */}
        <div className="drift-impact-row flex flex-wrap gap-2 items-center mt-3 text-sm">
          <span
            className={`drift-impact-badge px-2 py-0.5 rounded-full border text-xs uppercase tracking-wider ${
              impactLevel === "high"
                ? "bg-red-500/15 border-red-500/50"
                : impactLevel === "medium"
                ? "bg-amber-500/15 border-amber-500/50"
                : impactLevel === "low"
                ? "bg-emerald-500/15 border-emerald-500/50"
                : "opacity-70 border-white/12"
            }`}
          >
            Impact: {formatImpactLabel(impactLevel)}
          </span>
          {riskAreas.length > 0 && (
            <span className="drift-impact-risk opacity-80">
              Affects: {riskAreas.join(", ")}
            </span>
          )}
        </div>
      </div>

      {/* Summary */}
      <div>
        <h3 className="text-sm font-semibold text-slate-300 mb-1">Summary</h3>
        <p className="text-slate-200">{drift.summary}</p>
      </div>

      {/* Functionality */}
      <div>
        <h3 className="text-sm font-semibold text-slate-300 mb-1">Functionality</h3>
        <p className="text-slate-200">{drift.functionality}</p>
      </div>

      {/* Advantage (only when evidence exists) */}
      {advantageText && evidence && evidence.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-emerald-300 mb-1">Advantage</h3>
          <p className="text-slate-200">{advantageText}</p>
        </div>
      )}

      {/* Disadvantage */}
      {drift.disadvantage && (
        <div>
          <h3 className="text-sm font-semibold text-rose-300 mb-1">Disadvantage</h3>
          <p className="text-slate-200">{drift.disadvantage}</p>
        </div>
      )}

      {/* Root Cause */}
      {drift.root_cause && (
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-1">Root Cause</h3>
          <p className="text-slate-200">{drift.root_cause}</p>
        </div>
      )}

      {/* MMM: MENTOR — Recommended actions for this drift */}
      {recommendedActions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-2">Recommended Actions</h3>
          <ul className="list-disc list-inside space-y-1">
            {recommendedActions.map((action, idx) => (
              <li key={idx} className="text-slate-200 text-sm">
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Files Changed */}
      {drift.files_changed && drift.files_changed.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-2">Files Changed</h3>
          <ul className="list-disc list-inside space-y-1">
            {drift.files_changed.map((file, index) => (
              <li key={index} className="text-slate-200 text-sm">
                {file}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Metadata */}
      <div className="pt-4 border-t border-slate-800">
        <div className="text-xs text-slate-500 space-y-1">
          <p>Commit: {drift.commit_hash}</p>
          <p>Repository: {drift.repo_url}</p>
        </div>
      </div>

      {/* Conformance Evidence */}
      {(() => {
        const showConformance = drift?.driftType === "architecture" && drift?.classifier_mode_used === "conformance";
        if (!showConformance) {
          return (
            <div className="pt-4 border-t border-slate-800">
              <p className="text-xs text-slate-400">Conformance evidence applies only to Architecture drifts.</p>
            </div>
          );
        }
        return (
          <div className="pt-4 border-t border-slate-800 space-y-3">
            <h3 className="text-sm font-semibold text-slate-300">Conformance Evidence</h3>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span
                className={`px-2 py-0.5 rounded border ${
                  classificationInfo.tone === "positive"
                    ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-200"
                    : classificationInfo.tone === "neutral"
                    ? "bg-amber-500/15 border-amber-500/40 text-amber-200"
                    : "bg-rose-500/15 border-rose-500/40 text-rose-200"
                }`}
              >
                {classificationInfo.label}
              </span>
              {reasonCodes.length > 0 && (
                <span className="text-slate-300">Reasons: {reasonCodes.join(", ")}</span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2 text-sm text-slate-200">
              <div>Edges added: {drift.edges_added_count ?? 0}</div>
              <div>Edges removed: {drift.edges_removed_count ?? 0}</div>
              <div>Forbidden added: {drift.forbidden_edges_added_count ?? 0}</div>
              <div>Forbidden removed: {drift.forbidden_edges_removed_count ?? 0}</div>
              <div>Cycles added: {drift.cycles_added_count ?? 0}</div>
              <div>Cycles removed: {drift.cycles_removed_count ?? 0}</div>
            </div>

            {(drift.baseline_hash || drift.rules_hash) && (
              <div className="text-xs text-slate-400 space-y-1">
                {drift.baseline_hash && <div>Baseline hash: {drift.baseline_hash}</div>}
                {drift.rules_hash && <div>Rules hash: {drift.rules_hash}</div>}
              </div>
            )}

            <div className="space-y-1">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
                Evidence (top 10)
              </h4>
              {(() => {
                // Calculate total violation count
                const forbiddenAdded = drift.forbidden_edges_added_count ?? 0;
                const forbiddenRemoved = drift.forbidden_edges_removed_count ?? 0;
                const cyclesAdded = drift.cycles_added_count ?? 0;
                const cyclesRemoved = drift.cycles_removed_count ?? 0;
                const totalViolations = forbiddenAdded + forbiddenRemoved + cyclesAdded + cyclesRemoved;
                
                // If all counts are 0, show neutral message
                if (totalViolations === 0) {
                  return (
                    <p className="text-xs text-slate-400">No conformance violations detected for this commit.</p>
                  );
                }
                
                // If counts > 0 but evidence is missing, show error message
                if (totalViolations > 0 && (!evidence || evidence.length === 0)) {
                  return (
                    <p className="text-xs text-amber-400">
                      Evidence missing (unexpected). Please re-run analysis or report a bug.
                    </p>
                  );
                }
                
                // If evidence exists, render it
                if (evidence && evidence.length > 0) {
                  return (
                    <ul className="space-y-1">
                      {evidence.slice(0, 10).map((ev, idx) => (
                        <li key={idx} className="text-xs text-slate-200 border border-slate-800 rounded px-2 py-1">
                          <div className="flex flex-wrap gap-2">
                            {ev.direction && (
                              <span className="font-semibold">
                                {ev.direction === "added" ? "Added" : "Removed"}
                              </span>
                            )}
                            <span>{ev.from_module} → {ev.to_module}</span>
                          </div>
                          <div className="text-slate-400">{ev.src_file}</div>
                          {ev.import_text && <div className="text-slate-400 italic">import: {ev.import_text}</div>}
                        </li>
                      ))}
                    </ul>
                  );
                }
                
                // Fallback (should not reach here)
                return (
                  <p className="text-xs text-slate-400">No evidence provided.</p>
                );
              })()}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

export default DriftDetailPanel;

