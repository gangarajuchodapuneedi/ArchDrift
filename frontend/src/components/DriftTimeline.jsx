import DriftNode from "./DriftNode";

const BASELINE_REASON_CODES = ["BASELINE_MISSING", "BASELINE_EMPTY", "MAPPING_TOO_LOW", "NO_SOURCE_FILES"];

// DriftTimeline: Main container component that renders the tree map layout
// DriftNode: Individual drift item component that renders each node with card, badges, and branch
function DriftTimeline({ drifts, selectedDriftId, onSelectDrift, baselineStatus }) {
  // Sort drifts by date ascending (oldest first)
  const sortedDrifts = [...drifts].sort((a, b) => {
    return new Date(a.date) - new Date(b.date);
  });

  const selectedDrift = sortedDrifts.find((d) => d.id === selectedDriftId);
  const selectedReasonCodes = selectedDrift?.reason_codes ?? selectedDrift?.reasonCodes ?? [];
  const hasBaselineReason = selectedReasonCodes.some((r) => BASELINE_REASON_CODES.includes(r));
  const baselineHealth = baselineStatus?.baseline_health;
  const baselineNotReady =
    !!baselineHealth && (baselineHealth.baseline_ready === false || baselineHealth.mapping_ready === false);
  const showBaselineBanner = hasBaselineReason || baselineNotReady;

  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Drift Timeline</h2>
      {showBaselineBanner && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-3 text-amber-100">
          <div className="text-sm font-semibold">Baseline not ready</div>
          <p className="text-sm text-amber-50/90 mt-1">
            Conformance needs a real baseline + rules to compare. Generate + approve a baseline, then re-run analysis.
          </p>
        </div>
      )}
      <div className="drift-tree-container relative h-full">
        {/* Central trunk line */}
        <div className="drift-tree-line absolute left-1/2 -translate-x-1/2 top-0 bottom-0 w-0.5 bg-slate-700/50" />
        
        {/* Tree items container */}
        <div className="drift-tree-items flex flex-col gap-8 py-4">
          {sortedDrifts.map((drift, index) => (
            <DriftNode
              key={drift.id}
              drift={drift}
              index={index}
              isSelected={drift.id === selectedDriftId}
              onClick={() => onSelectDrift(drift.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default DriftTimeline;

