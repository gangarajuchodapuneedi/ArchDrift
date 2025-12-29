import { useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import DriftTimeline from "./components/DriftTimeline";
import DriftDetailPanel from "./components/DriftDetailPanel";
import OnboardingWizard from "./components/OnboardingWizard";
import { mockDrifts } from "./mockDrifts";
import { fetchDrifts, analyzeRepo } from "./api/client";
import { getPrimaryClassification } from "./components/classificationUtils";

// Main container component responsible for Mirror: repo-level summary + drift map
function App() {
  const [drifts, setDrifts] = useState([]);
  const [selectedDriftId, setSelectedDriftId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [repoUrl, setRepoUrl] = useState("https://github.com/git/git");
  const [maxCommits, setMaxCommits] = useState(30);
  const [maxDrifts, setMaxDrifts] = useState(5);
  const [classifierMode, setClassifierMode] = useState(
    localStorage.getItem("archdrift.classifier_mode") || "keywords"
  );
  const [analyzeStatus, setAnalyzeStatus] = useState("");
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [activeRepo, setActiveRepo] = useState(null);

  useEffect(() => {
    async function loadInitialDrifts() {
      setLoading(true);
      setError(null);
      try {
        const items = await fetchDrifts();
        const list = items && items.length > 0 ? items : mockDrifts;
        setDrifts(list);
        if (list.length > 0) {
          // Check if any drift has classifier_mode_used === "conformance" to determine mode
          const isConformanceMode = list.some((d) => d.classifier_mode_used === "conformance");
          const mode = isConformanceMode ? "conformance" : classifierMode;
          const defaultId = findDefaultDriftId(list, mode);
          if (defaultId) {
            setSelectedDriftId(defaultId);
          }
        }
      } catch (err) {
        console.error("Failed to fetch drifts, falling back to mock data:", err);
        setError("Could not load drifts from backend, showing mock data.");
        setDrifts(mockDrifts);
        if (mockDrifts.length > 0) {
          setSelectedDriftId(mockDrifts[0].id);
        }
      } finally {
        setLoading(false);
      }
    }

    loadInitialDrifts();
  }, []);

  // Load active repo from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("archdrift.activeRepo");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          // Validate required keys
          if (parsed && typeof parsed === "object" && 
              typeof parsed.repoUrl === "string" &&
              typeof parsed.repoPath === "string" &&
              typeof parsed.repoName === "string") {
            setActiveRepo(parsed);
          }
        } catch (err) {
          // Invalid JSON, treat as no active repo
        }
      }
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }, []);

  const selectedDrift = drifts.find((d) => d.id === selectedDriftId) || null;

  // Helper function to format drift type (reused from DriftNode logic)
  function formatDriftType(driftType) {
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
  }

  // Compute health summary metrics (MMM: Mirror)
  function getTopDriftType(drifts) {
    const counts = {};
    for (const d of drifts) {
      if (!d.driftType) continue;
      counts[d.driftType] = (counts[d.driftType] || 0) + 1;
    }
    const entries = Object.entries(counts);
    if (entries.length === 0) return null;
    const [topType] = entries.sort((a, b) => b[1] - a[1])[0];
    return topType || null;
  }

  function getTopTeam(drifts) {
    const counts = {};
    for (const d of drifts) {
      (d.teams || []).forEach((team) => {
        counts[team] = (counts[team] || 0) + 1;
      });
    }
    const entries = Object.entries(counts);
    if (entries.length === 0) return null;
    const [topTeam] = entries.sort((a, b) => b[1] - a[1])[0];
    return topTeam || null;
  }

  const totalDrifts = drifts.length;
  const positiveCount = drifts.filter((d) => getPrimaryClassification(d) === "positive").length;
  const negativeCount = drifts.filter((d) => getPrimaryClassification(d) === "negative").length;
  const noChangeCount = drifts.filter((d) => getPrimaryClassification(d) === "no_change").length;
  const needsReviewCount = drifts.filter((d) => getPrimaryClassification(d) === "needs_review").length;
  const unknownCount = drifts.filter((d) => getPrimaryClassification(d) === "unknown").length;
  const topDriftType = getTopDriftType(drifts);
  const topTeam = getTopTeam(drifts);

  // Helper function to find a drift with conformance violations
  // Returns the first drift with violations, or the first drift if none found
  function findDefaultDriftId(driftsList, mode) {
    if (!driftsList || driftsList.length === 0) {
      return null;
    }
    
    // Only apply violation-based selection in conformance mode
    if (mode === "conformance") {
      const violationDrift = driftsList.find((d) => {
        const forbiddenAdded = d.forbidden_edges_added_count ?? 0;
        const forbiddenRemoved = d.forbidden_edges_removed_count ?? 0;
        const cyclesAdded = d.cycles_added_count ?? 0;
        const cyclesRemoved = d.cycles_removed_count ?? 0;
        return forbiddenAdded > 0 || forbiddenRemoved > 0 || cyclesAdded > 0 || cyclesRemoved > 0;
      });
      
      if (violationDrift) {
        return violationDrift.id;
      }
    }
    
    // Fallback to first drift (current behavior)
    return driftsList[0].id;
  }

  async function handleAnalyzeRepo() {
    if (!repoUrl.trim()) {
      setAnalyzeStatus("Please enter a repository URL.");
      return;
    }
    setLoading(true);
    setError(null);
    setDrifts([]); // Clear previous drifts when starting new analysis
    setSelectedDriftId(null); // Clear selection
    setAnalyzeStatus("Analyzing repository for architectural drifts...");
    try {
      const driftsFromRepo = await analyzeRepo({
        repoUrl,
        maxCommits,
        maxDrifts,
        classifierMode,
      });
      if (!driftsFromRepo || driftsFromRepo.length === 0) {
        setAnalyzeStatus("No drifts detected (or response was empty).");
        setError("No drifts found. Try increasing max_commits or check if the repository has recent commits.");
        return;
      }
      setDrifts(driftsFromRepo);
      // In conformance mode, prefer selecting a drift with violations
      const defaultId = findDefaultDriftId(driftsFromRepo, classifierMode);
      if (defaultId) {
        setSelectedDriftId(defaultId);
      }
      setAnalyzeStatus(`Loaded ${driftsFromRepo.length} drifts from repo.`);
      setError(null); // Clear any previous errors
    } catch (err) {
      console.error("Error analyzing repo:", err);
      // Extract error message from axios error response
      let errorMessage = "Failed to analyze repository.";
      
      if (err.response) {
        // Server responded with error status
        errorMessage = err.response.data?.detail || err.response.statusText || `Server error (${err.response.status})`;
      } else if (err.request) {
        // Request was made but no response received (network error)
        if (err.code === "ECONNREFUSED" || err.message?.includes("Network Error") || err.message?.includes("ERR_NETWORK")) {
          errorMessage = "Cannot connect to backend server. Please ensure the backend is running on port 8000.";
        } else if (err.code === "ETIMEDOUT" || err.message?.includes("timeout")) {
          errorMessage = "Request timed out. The analysis may be taking too long. Try reducing max_commits.";
        } else {
          errorMessage = `Network error: ${err.message || "Unable to reach backend server"}`;
        }
      } else {
        // Something else happened
        errorMessage = err.message || "Failed to analyze repository.";
      }
      
      setError(errorMessage);
      setAnalyzeStatus(`Analysis failed: ${errorMessage}`);
      setDrifts([]); // Clear drifts on error
      setSelectedDriftId(null);
    } finally {
      setLoading(false);
    }
  }

  // Handle clear active repo
  function handleClearActiveRepo() {
    try {
      localStorage.removeItem("archdrift.activeRepo");
      setActiveRepo(null);
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar onOpenOnboarding={() => setIsOnboardingOpen(true)} />
      {activeRepo && (
        <div 
          data-testid="active-repo-banner"
          className="border-b border-slate-800 px-4 py-2 bg-slate-900/50 flex items-center justify-between gap-4"
        >
          <div className="flex items-center gap-2 text-sm text-slate-300">
            <span>Active Repo:</span>
            <span className="text-slate-100 font-medium" data-testid="active-repo-name">
              {activeRepo.repoName}
            </span>
            <span>—</span>
            <span className="text-slate-200 font-mono text-xs" data-testid="active-repo-path">
              {activeRepo.repoPath}
            </span>
            {activeRepo.lastApprovedBaselineHash && (
              <>
                <span className="text-slate-400">|</span>
                <span className="text-slate-400">Baseline:</span>
                <span className="text-slate-200 font-mono text-xs" data-testid="active-repo-baseline">
                  {activeRepo.lastApprovedBaselineHash}
                </span>
              </>
            )}
          </div>
          <div className="flex gap-2">
            <button
              data-testid="active-repo-change"
              onClick={() => setIsOnboardingOpen(true)}
              className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white"
            >
              Change
            </button>
            <button
              data-testid="active-repo-clear"
              onClick={handleClearActiveRepo}
              className="inline-flex items-center justify-center rounded-md bg-slate-700 hover:bg-slate-600 px-3 py-1.5 text-sm font-medium text-white"
            >
              Clear
            </button>
          </div>
        </div>
      )}
      <section className="border-b border-slate-800 px-4 py-3 bg-slate-900/50">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="flex-1 flex flex-col gap-2 md:flex-row md:items-center">
            <label className="text-sm text-slate-300 md:w-32">Repo URL</label>
            <input
              className="flex-1 rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-slate-100"
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
            />
            <input
              className="w-24 rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-slate-100"
              type="number"
              min={1}
              value={maxCommits}
              onChange={(e) => setMaxCommits(Number(e.target.value) || 1)}
            />
            <input
              className="w-20 rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-slate-100"
              type="number"
              min={1}
              value={maxDrifts}
              onChange={(e) => setMaxDrifts(Number(e.target.value) || 1)}
            />
            <select
              className="w-32 rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-slate-100"
              value={classifierMode}
              onChange={(e) => {
                const mode = e.target.value;
                setClassifierMode(mode);
                localStorage.setItem("archdrift.classifier_mode", mode);
              }}
            >
              <option value="keywords">keywords</option>
              <option value="conformance">conformance</option>
            </select>
            <button
              type="button"
              className="mt-2 md:mt-0 inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              onClick={handleAnalyzeRepo}
              disabled={loading}
            >
              {loading ? "Analyzing..." : "Analyze Repo"}
            </button>
          </div>
          {analyzeStatus && (
            <p className="text-xs text-slate-400 mt-2 md:mt-0">{analyzeStatus}</p>
          )}
        </div>
      </section>
      {error && (
        <div className="px-4 py-2 text-sm text-amber-300 bg-amber-900/20 border-b border-amber-800">
          {error}
        </div>
      )}
      <main className="flex-1 flex flex-row gap-4 p-4">
        <section className="w-1/2 border-r border-slate-800 pr-4 overflow-y-auto">
          {/* MMM: MIRROR (repo-level health summary for this analysis window) */}
          {totalDrifts > 0 && (
            <div className="health-summary-bar flex flex-col gap-1 mb-4 p-3 rounded-lg bg-white/[0.02] border border-white/[0.08]">
              <div className="health-summary-main flex flex-wrap gap-2 items-baseline justify-between">
                <span className="health-summary-label text-xs uppercase tracking-wider opacity-70">
                  Repo Health
                </span>
                <span className="health-summary-value text-sm">
                  In this analysis window:{" "}
                  <strong>{totalDrifts}</strong> drifts (
                  <span className="health-summary-positive text-emerald-400">
                    {positiveCount} positive
                  </span>
                  ,{" "}
                  <span className="health-summary-negative text-rose-400">
                    {negativeCount} negative
                  </span>
                  , <span className="text-slate-400">{noChangeCount} no change</span>
                  , <span className="text-amber-400">{needsReviewCount} needs review</span>
                  , <span className="text-slate-500">{unknownCount} unknown</span>
                  )
                </span>
              </div>

              <div className="health-summary-secondary flex flex-wrap gap-2 mt-1 text-xs opacity-90">
                {topDriftType && (
                  <span className="health-summary-chip px-2 py-0.5 rounded-full border border-white/[0.12]">
                    Most affected area: {formatDriftType(topDriftType)}
                  </span>
                )}
                {topTeam && (
                  <span className="health-summary-chip px-2 py-0.5 rounded-full border border-white/[0.12]">
                    Most impacted team: {topTeam}
                  </span>
                )}
              </div>
            </div>
          )}
          <DriftTimeline
            drifts={drifts}
            selectedDriftId={selectedDriftId}
            onSelectDrift={setSelectedDriftId}
          />
        </section>
        <section className="w-1/2 pl-4 overflow-y-auto">
          {loading && (
            <div className="text-sm text-slate-400 mb-2">Loading...</div>
          )}
          <DriftDetailPanel drift={selectedDrift} />
        </section>
      </main>
      {isOnboardingOpen && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setIsOnboardingOpen(false)}
        >
          <div 
            role="dialog" 
            aria-modal="true"
            data-testid="onboarding-modal"
            className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-bold text-slate-100 mb-4">Legacy Onboarding</h2>
            <OnboardingWizard 
              onClose={() => setIsOnboardingOpen(false)} 
              onActiveRepoUpdated={setActiveRepo}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
