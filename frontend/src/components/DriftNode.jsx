function DriftNode({ drift, index, isSelected, onClick }) {
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const day = date.getDate();
    const month = date.toLocaleString("en-US", { month: "short" });
    const year = date.getFullYear();
    return `${day} ${month} ${year}`;
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
    return typeMap[driftType] || driftType.charAt(0).toUpperCase() + driftType.slice(1).replace(/_/g, " ");
  };

  const isPositive = drift.type === "positive";
  const isLeft = index % 2 === 0;

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className={`drift-tree-item flex items-center relative cursor-pointer transition-all ${
        isLeft ? "md:justify-start justify-start" : "md:justify-end justify-start"
      } ${isSelected ? "drift-tree-item-selected" : ""}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {/* Node wrapper with date and node dot - positioned at center (trunk line) */}
      <div className="drift-tree-node-wrapper absolute left-1/2 -translate-x-1/2 flex flex-col items-center shrink-0 z-10">
        {/* Date above node */}
        <div className="drift-tree-date text-xs text-slate-400 opacity-80 mb-2 whitespace-nowrap">
          {formatDate(drift.date)}
        </div>
        
        {/* Node with dot and branch */}
        <div className="drift-tree-node relative flex items-center">
          {/* Node dot */}
          <span
            className={`drift-tree-node-dot w-2.5 h-2.5 rounded-full z-10 ${
              isPositive ? "bg-emerald-500" : "bg-rose-500"
            } ${isSelected ? "ring-2 ring-offset-2 ring-offset-slate-950" : ""} ${
              isPositive && isSelected ? "ring-emerald-500" : ""
            } ${!isPositive && isSelected ? "ring-rose-500" : ""}`}
          />
          
          {/* Branch line from node to card */}
          <span
            className={`drift-tree-node-branch absolute h-0.5 ${
              isLeft 
                ? "right-1/2 w-12" 
                : "left-1/2 w-12"
            } ${
              isPositive ? "bg-emerald-500/60" : "bg-rose-500/60"
            }`}
          />
        </div>
      </div>

      {/* Card with drift content */}
      <div
        className={`drift-tree-card relative transition-all ${
          isSelected
            ? isPositive
              ? "bg-emerald-500/30 border-emerald-500"
              : "bg-rose-500/30 border-rose-500"
            : isPositive
            ? "bg-emerald-500/10 border-emerald-500/40 hover:bg-emerald-500/20"
            : "bg-rose-500/10 border-rose-500/40 hover:bg-rose-500/20"
        } border rounded-lg p-3 w-64 md:w-64 ${
          isLeft ? "md:mr-auto md:ml-16 ml-16" : "md:ml-auto md:mr-16 mr-16"
        } ${
          isSelected ? "ring-2 ring-offset-2 ring-offset-slate-950" : ""
        }`}
      >
        {/* Type badge, drift type badge, and team badges */}
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span
            className={`inline-block px-2 py-1 text-xs font-semibold rounded ${
              isPositive
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                : "bg-rose-500/20 text-rose-300 border border-rose-500/40"
            }`}
          >
            {drift.type}
          </span>
          {/* Drift type badge */}
          {drift.driftType && (
            <span className="inline-block px-2 py-0.5 text-xs font-medium rounded bg-blue-500/20 text-blue-300 border border-blue-500/40">
              {formatDriftType(drift.driftType)}
            </span>
          )}
          {/* Team badges */}
          {drift.teams && drift.teams.length > 0 && (
            <>
              {drift.teams.map((team) => (
                <span
                  key={team}
                  className="inline-block px-2 py-0.5 text-xs font-medium rounded bg-slate-700/50 text-slate-300 border border-slate-600/50"
                >
                  {team}
                </span>
              ))}
            </>
          )}
        </div>

        {/* Title */}
        <h3 className="text-sm font-medium text-slate-100">{drift.title}</h3>
      </div>
    </div>
  );
}

export default DriftNode;

