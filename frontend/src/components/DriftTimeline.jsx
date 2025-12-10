import DriftNode from "./DriftNode";

// DriftTimeline: Main container component that renders the tree map layout
// DriftNode: Individual drift item component that renders each node with card, badges, and branch
function DriftTimeline({ drifts, selectedDriftId, onSelectDrift }) {
  // Sort drifts by date ascending (oldest first)
  const sortedDrifts = [...drifts].sort((a, b) => {
    return new Date(a.date) - new Date(b.date);
  });

  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Drift Timeline</h2>
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

