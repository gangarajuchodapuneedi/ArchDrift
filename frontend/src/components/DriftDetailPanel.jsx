// Renders the MMM: Mirror + Mentor detail for a drift (what happened + what should I do next)
// Multiplier: Copy as ticket button allows exporting drift info as a formatted issue body
import { useState } from "react";

function DriftDetailPanel({ drift }) {
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
  const buildDriftTicketBody = (drift, formattedDate) => {
    const lines = [];
    const driftImpactLevel = drift.impactLevel ?? "unknown";
    const driftRiskAreas = drift.riskAreas ?? [];
    const driftRecommendedActions = drift.recommendedActions ?? [];

    lines.push(`# ${drift.title || "Architecture Drift"}`);
    lines.push("");
    lines.push("## Mirror — What happened");
    lines.push(`- Date: ${formattedDate}`);
    lines.push(`- Sentiment: ${drift.type}`);
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

  const isPositive = drift.type === "positive";
  const impactLevel = drift.impactLevel ?? "unknown";
  const riskAreas = drift.riskAreas ?? [];
  const recommendedActions = drift.recommendedActions ?? [];
  const formattedDate = formatDate(drift.date);

  const [copyStatus, setCopyStatus] = useState("");

  async function handleCopyTicket() {
    try {
      const body = buildDriftTicketBody(drift, formattedDate);
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

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
      {/* Header */}
      <div className="border-b border-slate-800 pb-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-2xl font-bold text-slate-100">{drift.title}</h2>
          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 text-sm font-semibold rounded ${
                isPositive
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : "bg-rose-500/20 text-rose-300 border border-rose-500/40"
              }`}
            >
              {drift.type}
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

      {/* Advantage */}
      {drift.advantage && (
        <div>
          <h3 className="text-sm font-semibold text-emerald-300 mb-1">Advantage</h3>
          <p className="text-slate-200">{drift.advantage}</p>
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
    </div>
  );
}

export default DriftDetailPanel;

